import threading
from window.run import run_gui
from audio.virtual_speaker import VirtualSpeaker
from ai.speech_recognizer import SpeechRecognizer
import queue

def main():
    # Create a queue for communication between threads
    text_queue = queue.Queue()
    
    # Initialize components
    speech_recognizer = SpeechRecognizer(text_queue)
    virtual_speaker = VirtualSpeaker(speech_recognizer.process_audio)
    
    # Start audio capture in separate thread
    audio_thread = threading.Thread(target=virtual_speaker.start_capture, daemon=True)
    audio_thread.start()
    
    # Start speech recognition in separate thread
    recognition_thread = threading.Thread(target=speech_recognizer.start_recognition, daemon=True)
    recognition_thread.start()
    
    # Run GUI (this blocks until window is closed)
    run_gui(text_queue)

if __name__ == "__main__":
    main()
