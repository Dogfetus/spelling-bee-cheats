import pyaudiowpatch as pyaudio
import numpy as np
import threading
import time
import queue

class AudioPassthrough:
    def __init__(self, chunk_size=1024, buffer_size=10):
        self.chunk_size = chunk_size
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.is_running = False
        
        # Audio buffer queue for thread-safe audio transfer
        self.audio_queue = queue.Queue(maxsize=buffer_size)
        
        # Threading
        self.input_thread = None
        self.output_thread = None
        
    def list_devices(self):
        """List all available devices"""
        print("\n=== OUTPUT DEVICES (Speakers/Headphones) ===")
        output_devices = []
        for device in self.audio.get_device_info_generator():
            if device['maxOutputChannels'] > 0:
                output_devices.append(device)
                print(f"{device['index']:2d}: {device['name']}")
                print(f"     Channels: {device['maxOutputChannels']}, Rate: {int(device['defaultSampleRate'])}")
        
        print("\n=== INPUT DEVICES (Microphones) ===")
        input_devices = []
        for device in self.audio.get_device_info_generator():
            if device['maxInputChannels'] > 0:
                input_devices.append(device)
                print(f"{device['index']:2d}: {device['name']}")
                print(f"     Channels: {device['maxInputChannels']}, Rate: {int(device['defaultSampleRate'])}")
        
        print("\n=== LOOPBACK DEVICES (System Audio Capture) ===")
        loopback_devices = []
        try:
            for device in self.audio.get_loopback_device_info_generator():
                loopback_devices.append(device)
                print(f"{device['index']:2d}: {device['name']} (Loopback)")
                print(f"     Channels: {device['maxInputChannels']}, Rate: {int(device['defaultSampleRate'])}")
        except Exception as e:
            print(f"No loopback devices: {e}")
        
        return output_devices, input_devices, loopback_devices
    
    def find_device_by_name(self, name_fragment, device_type="output"):
        """Find device by partial name match"""
        if device_type == "output":
            for device in self.audio.get_device_info_generator():
                if (device['maxOutputChannels'] > 0 and 
                    name_fragment.lower() in device['name'].lower()):
                    return device
        elif device_type == "input":
            for device in self.audio.get_device_info_generator():
                if (device['maxInputChannels'] > 0 and 
                    name_fragment.lower() in device['name'].lower()):
                    return device
        elif device_type == "loopback":
            try:
                for device in self.audio.get_loopback_device_info_generator():
                    if name_fragment.lower() in device['name'].lower():
                        return device
            except:
                pass
        return None
    
    def start_passthrough(self, input_device_name=None, output_device_name=None, 
                         input_device_type="loopback", volume_multiplier=1.0):
        """
        Start audio passthrough
        
        Args:
            input_device_name: Name fragment of input device
            output_device_name: Name fragment of output device  
            input_device_type: "loopback", "input", or "default_loopback"
            volume_multiplier: Volume adjustment (1.0 = original, 0.5 = half, 2.0 = double)
        """
        
        # Find input device
        if input_device_type == "default_loopback":
            try:
                input_device = self.audio.get_default_wasapi_loopback()
                print(f"Using default loopback: {input_device['name']}")
            except Exception as e:
                print(f"Could not get default loopback: {e}")
                return False
        elif input_device_name:
            input_device = self.find_device_by_name(input_device_name, input_device_type)
            if not input_device:
                print(f"Input device '{input_device_name}' not found!")
                return False
            print(f"Found input device: {input_device['name']}")
        else:
            print("No input device specified!")
            return False
        
        # Find output device
        if output_device_name:
            output_device = self.find_device_by_name(output_device_name, "output")
            if not output_device:
                print(f"Output device '{output_device_name}' not found!")
                return False
            print(f"Found output device: {output_device['name']}")
        else:
            # Use default output device
            try:
                output_device = self.audio.get_default_output_device_info()
                print(f"Using default output: {output_device['name']}")
            except Exception as e:
                print(f"Could not get default output: {e}")
                return False
        
        # Determine compatible audio format
        input_rate = int(input_device['defaultSampleRate'])
        output_rate = int(output_device['defaultSampleRate'])
        
        # Use the input device's sample rate (loopback devices are usually more reliable)
        sample_rate = input_rate
        
        input_channels = min(input_device['maxInputChannels'], 2)
        output_channels = min(output_device['maxOutputChannels'], 2)
        
        # Test if output device supports the input sample rate
        try:
            test_output = self.audio.open(
                format=pyaudio.paInt16,
                channels=output_channels,
                rate=sample_rate,
                output=True,
                output_device_index=output_device['index'],
                frames_per_buffer=self.chunk_size
            )
            test_output.close()
            print(f"✓ Output device supports {sample_rate} Hz")
        except Exception as e:
            print(f"✗ Output device doesn't support {sample_rate} Hz: {e}")
            # Try output device's preferred rate
            sample_rate = output_rate
            print(f"Trying output device's rate: {sample_rate} Hz")
        
        print(f"\nAudio Configuration:")
        print(f"Sample Rate: {sample_rate} Hz")
        print(f"Input Channels: {input_channels}")
        print(f"Output Channels: {output_channels}")
        print(f"Volume Multiplier: {volume_multiplier}")
        
        try:
            # Open input stream
            self.input_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=input_channels,
                rate=sample_rate,
                input=True,
                input_device_index=input_device['index'],
                frames_per_buffer=self.chunk_size
            )
            
            # Open output stream
            self.output_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=output_channels,
                rate=sample_rate,
                output=True,
                output_device_index=output_device['index'],
                frames_per_buffer=self.chunk_size
            )
            
            self.is_running = True
            
            # Input thread - captures audio
            def input_worker():
                while self.is_running:
                    try:
                        data = self.input_stream.read(self.chunk_size, exception_on_overflow=False)
                        audio_data = np.frombuffer(data, dtype=np.int16)
                        
                        # Apply volume adjustment
                        if volume_multiplier != 1.0:
                            audio_data = (audio_data * volume_multiplier).astype(np.int16)
                        
                        # Handle channel conversion
                        if input_channels != output_channels:
                            if input_channels == 2 and output_channels == 1:
                                # Stereo to mono
                                audio_data = audio_data.reshape(-1, 2)
                                audio_data = np.mean(audio_data, axis=1).astype(np.int16)
                            elif input_channels == 1 and output_channels == 2:
                                # Mono to stereo
                                audio_data = np.repeat(audio_data, 2)
                        
                        # Sample rate conversion if needed
                        if input_rate != sample_rate:
                            # Simple linear interpolation for sample rate conversion
                            ratio = sample_rate / input_rate
                            new_length = int(len(audio_data) * ratio)
                            
                            if output_channels == 2 and len(audio_data) % 2 == 0:
                                # Handle stereo data
                                stereo_data = audio_data.reshape(-1, 2)
                                left_resampled = np.interp(
                                    np.linspace(0, len(stereo_data), new_length // 2),
                                    np.arange(len(stereo_data)),
                                    stereo_data[:, 0]
                                ).astype(np.int16)
                                right_resampled = np.interp(
                                    np.linspace(0, len(stereo_data), new_length // 2),
                                    np.arange(len(stereo_data)),
                                    stereo_data[:, 1]
                                ).astype(np.int16)
                                audio_data = np.column_stack((left_resampled, right_resampled)).flatten()
                            else:
                                # Handle mono data
                                audio_data = np.interp(
                                    np.linspace(0, len(audio_data), new_length),
                                    np.arange(len(audio_data)),
                                    audio_data
                                ).astype(np.int16)
                        
                        # Put in queue (non-blocking, drop if full)
                        try:
                            self.audio_queue.put(audio_data.tobytes(), block=False)
                        except queue.Full:
                            # Drop frame if buffer is full to prevent latency buildup
                            try:
                                self.audio_queue.get_nowait()  # Remove oldest frame
                                self.audio_queue.put(audio_data.tobytes(), block=False)
                            except queue.Empty:
                                pass
                            
                    except Exception as e:
                        print(f"Input error: {e}")
                        break
            
            # Output thread - plays audio
            def output_worker():
                while self.is_running:
                    try:
                        # Get audio data from queue
                        audio_bytes = self.audio_queue.get(timeout=0.1)
                        self.output_stream.write(audio_bytes)
                    except queue.Empty:
                        # No audio data, write silence to prevent underruns
                        silence = np.zeros(self.chunk_size * output_channels, dtype=np.int16)
                        self.output_stream.write(silence.tobytes())
                    except Exception as e:
                        print(f"Output error: {e}")
                        break
            
            # Start threads
            self.input_thread = threading.Thread(target=input_worker, daemon=True)
            self.output_thread = threading.Thread(target=output_worker, daemon=True)
            
            self.input_thread.start()
            self.output_thread.start()
            
            print("✓ Audio passthrough started!")
            return True
            
        except Exception as e:
            print(f"Failed to start passthrough: {e}")
            self.stop_passthrough()
            return False
    
    def stop_passthrough(self):
        """Stop audio passthrough"""
        self.is_running = False
        
        # Stop and close streams
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        
        # Wait for threads to finish
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=1.0)
        if self.output_thread and self.output_thread.is_alive():
            self.output_thread.join(timeout=1.0)
        
        # Clear queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        print("Audio passthrough stopped")
    
    def __del__(self):
        self.stop_passthrough()
        self.audio.terminate()

# Example usage functions
def example_system_audio_to_headphones():
    """Route system audio from speakers to headphones"""
    passthrough = AudioPassthrough()
    
    # List devices to see what's available
    passthrough.list_devices()
    
    # Route default system audio to headphones
    if passthrough.start_passthrough(
        input_device_type="default_loopback",  # Capture system audio
        output_device_name="Headphones",       # Send to headphones
        volume_multiplier=0.8                  # Reduce volume slightly
    ):
        print("\n🎵 Routing system audio to headphones...")
        print("Play some system audio to test!")
        return passthrough
    return None

def example_microphone_to_speakers():
    """Route microphone audio to speakers (creates feedback loop!)"""
    passthrough = AudioPassthrough()
    
    if passthrough.start_passthrough(
        input_device_name="Microphone",     # Capture from mic
        input_device_type="input",
        output_device_name="Speakers",      # Send to speakers
        volume_multiplier=0.5               # Lower volume to reduce feedback
    ):
        print("\n🎤 Routing microphone to speakers...")
        print("⚠️  WARNING: This may create audio feedback!")
        return passthrough
    return None

def example_specific_device_routing():
    """Route audio from one specific device to another"""
    passthrough = AudioPassthrough()
    
    # Show available devices
    passthrough.list_devices()
    
    if passthrough.start_passthrough(
        input_device_name="Realtek",        # Capture from Realtek loopback
        input_device_type="loopback",
        output_device_name="HyperX",        # Send to HyperX headset
        volume_multiplier=1.0
    ):
        print("\n🔄 Custom device routing active...")
        return passthrough
    return None

def interactive_device_selection():
    """Interactive device selection with numbered choices"""
    passthrough = AudioPassthrough()
    
    # Get all devices
    output_devices, input_devices, loopback_devices = passthrough.list_devices()
    
    print("\n" + "="*50)
    print("INTERACTIVE DEVICE SELECTION")
    print("="*50)
    
    # Choose input device type
    print("\n🎵 STEP 1: Choose INPUT source type:")
    print("1: Loopback (capture what's playing on speakers)")
    print("2: Microphone (capture from mic)")
    
    input_type_choice = input("Enter choice (1-2): ").strip()
    
    if input_type_choice == "1":
        # Loopback devices
        if not loopback_devices:
            print("❌ No loopback devices available!")
            return None
            
        print("\n🔊 Available LOOPBACK devices:")
        for i, device in enumerate(loopback_devices, 1):
            print(f"{i:2d}: {device['name']}")
        
        try:
            choice = int(input(f"\nSelect loopback device (1-{len(loopback_devices)}): ")) - 1
            if 0 <= choice < len(loopback_devices):
                input_device = loopback_devices[choice]
                input_device_type = "loopback"
            else:
                print("Invalid choice!")
                return None
        except ValueError:
            print("Invalid input!")
            return None
            
    elif input_type_choice == "2":
        # Microphone devices
        if not input_devices:
            print("❌ No input devices available!")
            return None
            
        print("\n🎤 Available MICROPHONE devices:")
        for i, device in enumerate(input_devices, 1):
            print(f"{i:2d}: {device['name']}")
        
        try:
            choice = int(input(f"\nSelect microphone (1-{len(input_devices)}): ")) - 1
            if 0 <= choice < len(input_devices):
                input_device = input_devices[choice]
                input_device_type = "input"
            else:
                print("Invalid choice!")
                return None
        except ValueError:
            print("Invalid input!")
            return None
    else:
        print("Invalid choice!")
        return None
    
    # Choose output device
    if not output_devices:
        print("❌ No output devices available!")
        return None
        
    print("\n🎧 STEP 2: Choose OUTPUT destination:")
    for i, device in enumerate(output_devices, 1):
        print(f"{i:2d}: {device['name']}")
    
    try:
        choice = int(input(f"\nSelect output device (1-{len(output_devices)}): ")) - 1
        if 0 <= choice < len(output_devices):
            output_device = output_devices[choice]
        else:
            print("Invalid choice!")
            return None
    except ValueError:
        print("Invalid input!")
        return None
    
    # Volume adjustment
    print("\n🔊 STEP 3: Volume adjustment:")
    print("1.0 = Normal volume")
    print("0.5 = Half volume")
    print("2.0 = Double volume")
    
    try:
        volume = float(input("Enter volume multiplier (default 1.0): ") or "1.0")
    except ValueError:
        volume = 1.0
    
    # Show configuration
    print("\n" + "="*50)
    print("ROUTING CONFIGURATION")
    print("="*50)
    print(f"📥 INPUT:  {input_device['name']}")
    print(f"📤 OUTPUT: {output_device['name']}")
    print(f"🔊 VOLUME: {volume}x")
    print("="*50)
    
    confirm = input("\nStart routing? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return None
    
    # Start the routing using device indices directly
    try:
        # Modify the start_passthrough to accept device objects directly
        sample_rate = int(input_device['defaultSampleRate'])
        input_channels = min(input_device['maxInputChannels'], 2)
        output_channels = min(output_device['maxOutputChannels'], 2)
        
        # Open streams directly
        passthrough.input_stream = passthrough.audio.open(
            format=pyaudio.paInt16,
            channels=input_channels,
            rate=sample_rate,
            input=True,
            input_device_index=input_device['index'],
            frames_per_buffer=passthrough.chunk_size
        )
        
        passthrough.output_stream = passthrough.audio.open(
            format=pyaudio.paInt16,
            channels=output_channels,
            rate=sample_rate,
            output=True,
            output_device_index=output_device['index'],
            frames_per_buffer=passthrough.chunk_size
        )
        
        passthrough.is_running = True
        
        # Simple passthrough loop (blocking)
        print("✅ Routing started! Press Ctrl+C to stop...")
        
        import threading
        import queue
        
        # Use the existing threading logic from the original script
        audio_queue = queue.Queue(maxsize=10)
        
        def input_worker():
            while passthrough.is_running:
                try:
                    data = passthrough.input_stream.read(passthrough.chunk_size, exception_on_overflow=False)
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    # Apply volume adjustment
                    if volume != 1.0:
                        audio_data = (audio_data * volume).astype(np.int16)
                    
                    # Handle channel conversion if needed
                    if input_channels != output_channels:
                        if input_channels == 2 and output_channels == 1:
                            audio_data = audio_data.reshape(-1, 2)
                            audio_data = np.mean(audio_data, axis=1).astype(np.int16)
                        elif input_channels == 1 and output_channels == 2:
                            audio_data = np.repeat(audio_data, 2)
                    
                    try:
                        audio_queue.put(audio_data.tobytes(), block=False)
                    except queue.Full:
                        try:
                            audio_queue.get_nowait()
                            audio_queue.put(audio_data.tobytes(), block=False)
                        except queue.Empty:
                            pass
                            
                except Exception as e:
                    print(f"Input error: {e}")
                    break
        
        def output_worker():
            while passthrough.is_running:
                try:
                    audio_bytes = audio_queue.get(timeout=0.1)
                    passthrough.output_stream.write(audio_bytes)
                except queue.Empty:
                    silence = np.zeros(passthrough.chunk_size * output_channels, dtype=np.int16)
                    passthrough.output_stream.write(silence.tobytes())
                except Exception as e:
                    print(f"Output error: {e}")
                    break
        
        # Start threads
        input_thread = threading.Thread(target=input_worker, daemon=True)
        output_thread = threading.Thread(target=output_worker, daemon=True)
        
        input_thread.start()
        output_thread.start()
        
        return passthrough
        
    except Exception as e:
        print(f"❌ Failed to start routing: {e}")
        return None

# Replace the main section with this interactive version
if __name__ == "__main__":
    print("🎵 Interactive Audio Passthrough")
    print("1: Quick Examples (Hardcoded)")
    print("2: Interactive Device Selection")
    print("3: List Devices Only")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    passthrough = None
    
    if choice == "1":
        # Original examples
        print("\n1: System Audio → Headphones")
        print("2: Microphone → Speakers")
        print("3: Custom Device Routing")
        
        sub_choice = input("Enter choice (1-3): ").strip()
        
        if sub_choice == "1":
            passthrough = example_system_audio_to_headphones()
        elif sub_choice == "2":
            passthrough = example_microphone_to_speakers()
        elif sub_choice == "3":
            passthrough = example_specific_device_routing()
            
    elif choice == "2":
        # New interactive selection
        passthrough = interactive_device_selection()
        
    elif choice == "3":
        AudioPassthrough().list_devices()
    else:
        print("Invalid choice")
        exit()
    
    if passthrough:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping passthrough...")
            passthrough.stop_passthrough()
    
    print("Done!")