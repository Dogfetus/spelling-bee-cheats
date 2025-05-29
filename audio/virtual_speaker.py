import sounddevice as sd
import numpy as np
import queue

class VirtualSpeaker:
    def __init__(self, audio_callback):
        self.audio_callback = audio_callback
        self.audio_queue = queue.Queue()
        self.sample_rate = 44100
        self.channels = 2
        self.running = False
        
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
    
    def start_capture(self):
        """Start capturing audio from the virtual speaker"""
        self.running = True
        
        try:
            # List available audio devices
            print("Available audio devices:")
            print(sd.query_devices())
            
            # Start audio stream
            with sd.InputStream(
                callback=self.audio_input_callback,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=1024
            ):
                print("Virtual speaker is listening...")
                while self.running:
                    if not self.audio_queue.empty():
                        audio_chunk = self.audio_queue.get()
                        self.audio_callback(audio_chunk, self.sample_rate)
                    
        except Exception as e:
            print(f"Error starting audio capture: {e}")
    
    def stop_capture(self):
        """Stop audio capture"""
        self.running = False
