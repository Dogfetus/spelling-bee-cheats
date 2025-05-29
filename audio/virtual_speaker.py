import sounddevice as sd
import numpy as np
import queue
import threading
import subprocess
import os

class VirtualSpeaker:
    def __init__(self, audio_callback):
        self.audio_callback = audio_callback
        self.audio_queue = queue.Queue()
        self.sample_rate = 48000  # Changed from 44100 to 48000 to match PipeWire default
        self.channels = 2
        self.running = False
        
        # Try to setup virtual audio device automatically
        self.setup_virtual_audio()
        
    def setup_virtual_audio(self):
        """Create virtual audio device if it doesn't exist"""
        try:
            print("Checking for virtual audio device...")
            
            # Check if virtual_speaker already exists
            result = subprocess.run(['pactl', 'list', 'short', 'sinks'], 
                                  capture_output=True, text=True, check=True)
            
            if 'virtual_speaker' not in result.stdout:
                print("Creating virtual audio device...")
                
                # Create the virtual sink
                create_result = subprocess.run(['pactl', 'load-module', 'module-null-sink', 
                              'sink_name=virtual_speaker', 
                              'sink_properties=device.description="Virtual_Speaker"'], 
                              capture_output=True, text=True, check=True)
                
                if create_result.stdout.strip():
                    print(f"Virtual sink created with module ID: {create_result.stdout.strip()}")
                
                # Create loopback to default sink so you can still hear audio
                loopback_result = subprocess.run(['pactl', 'load-module', 'module-loopback', 
                              'source=virtual_speaker.monitor', 
                              'sink=@DEFAULT_SINK@'], 
                              capture_output=True, text=True, check=True)
                
                if loopback_result.stdout.strip():
                    print(f"Loopback created with module ID: {loopback_result.stdout.strip()}")
                
                # Refresh audio system
                print("Refreshing audio system...")
                subprocess.run(['pactl', 'exit'], capture_output=True)
                
                print("✅ Virtual audio device created successfully!")
                print("💡 You can now:")
                print("   1. Set 'Virtual_Speaker' as your default audio device, OR")
                print("   2. Use pavucontrol to route specific apps to 'Virtual_Speaker'")
                print("   3. Or run: pactl set-default-sink virtual_speaker")
                
            else:
                print("✅ Virtual audio device already exists")
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Could not create virtual audio device: {e}")
            print("🔧 Please install PulseAudio or run manually:")
            print("   pactl load-module module-null-sink sink_name=virtual_speaker")
            
        except FileNotFoundError:
            print("❌ PulseAudio (pactl) not found")
            print("🔧 Please install PulseAudio:")
            print("   sudo apt install pulseaudio-utils  # Ubuntu/Debian")
            print("   sudo dnf install pulseaudio-utils  # Fedora")
            
        except Exception as e:
            print(f"❌ Unexpected error setting up virtual audio: {e}")
    
        
    def find_virtual_device(self):
        """Find the virtual speaker device"""
        devices = sd.query_devices()
        print("\nAvailable audio devices:")
        for i, device in enumerate(devices):
            print(f"  {i} {device['name']}, {device['hostapi']} ({device['max_input_channels']} in, {device['max_output_channels']} out)")
            
        # Look specifically for virtual_speaker.monitor
        for i, device in enumerate(devices):
            device_name = device['name'].lower()
            if 'virtual_speaker' in device_name and device['max_input_channels'] > 0:
                print(f"🎯 Found virtual device: {device['name']} (device {i})")
                return i
                
        # Look for any virtual device monitor
        for i, device in enumerate(devices):
            device_name = device['name'].lower()
            if 'virtual' in device_name and 'monitor' in device_name and device['max_input_channels'] > 0:
                print(f"🎯 Found virtual monitor device: {device['name']} (device {i})")
                return i
        
        # Look for any monitor device as fallback
        for i, device in enumerate(devices):
            if 'monitor' in device['name'].lower() and device['max_input_channels'] > 0:
                print(f"📻 Using monitor device: {device['name']} (device {i})")
                return i
        
        # Fallback to default input
        print("⚠️  No virtual/monitor device found, using default input")
        print("💡 This will capture microphone instead of system audio")
        return None
        
    def audio_input_callback(self, indata, frames, time, status):
        """Callback for audio input"""
        if status:
            print(f"Audio status: {status}")
        
        # Convert to mono if stereo
        if self.channels == 2:
            audio_data = np.mean(indata, axis=1)
        else:
            audio_data = indata[:, 0]
            
        # Put audio data in queue for processing
        self.audio_queue.put(audio_data.copy())
    
    def get_device_sample_rate(self, device_id):
        """Get the sample rate for a specific device"""
        try:
            if device_id is not None:
                device_info = sd.query_devices(device_id)
                if 'default_samplerate' in device_info:
                    return int(device_info['default_samplerate'])
        except:
            pass
        return 48000  # Default fallback
    
    def start_capture(self):
        """Start capturing audio from the virtual speaker"""
        self.running = True
        
        try:
            # Find the virtual device
            device_id = self.find_virtual_device()
            
            # Get the correct sample rate for this device
            device_sample_rate = self.get_device_sample_rate(device_id)
            print(f"🎵 Using sample rate: {device_sample_rate} Hz")
            
            if device_id is None:
                print("🎤 Capturing from default microphone...")
            else:
                print("🔊 Capturing from virtual audio device...")
            
            # Start audio stream with correct sample rate
            with sd.InputStream(
                device=device_id,
                callback=self.audio_input_callback,
                channels=self.channels,
                samplerate=device_sample_rate,
                blocksize=1024
            ):
                print("🎧 Virtual speaker is listening...")
                if device_id is not None:
                    print("💡 Play some audio/video and watch for speech recognition!")
                
                while self.running:
                    if not self.audio_queue.empty():
                        audio_chunk = self.audio_queue.get()
                        # Use the device's actual sample rate
                        self.audio_callback(audio_chunk, device_sample_rate)
                    
        except Exception as e:
            print(f"❌ Error starting audio capture: {e}")
            print("🔧 Try checking your audio devices or permissions")
    
    def stop_capture(self):
        """Stop audio capture"""
        self.running = False
