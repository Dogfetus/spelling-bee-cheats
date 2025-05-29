import speech_recognition as sr
import numpy as np
import io
import wave
import queue

class SpeechRecognizer:
    def __init__(self, text_queue):
        self.recognizer = sr.Recognizer()
        self.text_queue = text_queue
        self.audio_queue = queue.Queue()
        self.running = False
        
        # Adjust for ambient noise
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        
    def process_audio(self, audio_data, sample_rate):
        """Process incoming audio data"""
        # Convert numpy array to audio format that speech_recognition can use
        self.audio_queue.put((audio_data, sample_rate))
    
    def start_recognition(self):
        """Start the speech recognition loop"""
        self.running = True
        
        while self.running:
            try:
                if not self.audio_queue.empty():
                    audio_data, sample_rate = self.audio_queue.get()
                    
                    # Convert numpy array to AudioData object
                    audio_bytes = self.numpy_to_wav_bytes(audio_data, sample_rate)
                    audio_data_obj = sr.AudioData(audio_bytes, sample_rate, 2)
                    
                    # Recognize speech
                    try:
                        text = self.recognizer.recognize_google(audio_data_obj)
                        if text.strip():
                            print(f"Recognized: {text}")
                            self.text_queue.put(text)
                    except sr.UnknownValueError:
                        pass  # No speech detected
                    except sr.RequestError as e:
                        print(f"Speech recognition error: {e}")
                        
            except Exception as e:
                print(f"Recognition error: {e}")
    
    def numpy_to_wav_bytes(self, audio_data, sample_rate):
        """Convert numpy array to WAV bytes"""
        # Normalize audio data
        audio_data = np.clip(audio_data, -1.0, 1.0)
        audio_data = (audio_data * 32767).astype(np.int16)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data.tobytes())
        
        return wav_buffer.getvalue()
    
    def stop_recognition(self):
        """Stop speech recognition"""
        self.running = False
