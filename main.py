import os
import cv2
import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QVBoxLayout, QHBoxLayout,
                            QFileDialog, QSlider, QLabel, QStyle, QMessageBox,
                            QInputDialog, QApplication)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl, QObject, pyqtSignal, pyqtSlot, QMetaObject, Qt, QThread
import threading
import speech_recognition as sr
from pytube import YouTube
import tempfile
from datetime import datetime

# Global variable for the path
PATH_TO_DIRECTORY = os.path.join(os.path.expanduser('~'), 'Documents/ai-projects/video_assistant/path_to_obsidian')

class SignalHelper(QObject):
    show_message = pyqtSignal(str, str)  # Signal for showing messages
    
class ListenThread(QThread):
    command_received = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = False
        self.should_stop = False

    def run(self):
        # Initialize microphone once
        with self.microphone as source:
            print("Adjusting for ambient noise...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        
        while not self.should_stop:
            if self.is_listening:
                try:
                    with self.microphone as source:
                        print("Listening for command...")
                        audio = self.recognizer.listen(source, phrase_time_limit=5)
                    
                    if not self.is_listening:  # Check if we should still process the audio
                        continue
                        
                    command = self.recognizer.recognize_google(audio).lower()
                    print(f"Command received: {command}")
                    self.command_received.emit(command)
                    
                except Exception as e:
                    print(f"Error occurred: {e}")
                
                self.is_listening = False  # Stop listening after processing one command
            else:
                self.msleep(100)  # Small delay when not listening

    def start_listening(self):
        self.is_listening = True
        print("Started listening...")

    def stop_listening(self):
        self.is_listening = False
        print("Stopped listening...")

    def stop(self):
        self.should_stop = True
        self.is_listening = False

class VideoPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice-Controlled Video Player")
        self.setGeometry(350, 100, 700, 500)
        self.temp_dir = tempfile.gettempdir()
        self.current_video_path = None
        
        # Initialize signal helper
        self.signal_helper = SignalHelper()
        self.signal_helper.show_message.connect(self.show_message_box)
        
        # Initialize listen thread
        self.listen_thread = ListenThread()
        self.listen_thread.command_received.connect(self.handle_command)
        self.listen_thread.start()
        
        self.init_ui()

    @pyqtSlot(str, str)
    def show_message_box(self, title, message):
        QMessageBox.information(self, title, message)

    def init_ui(self):
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoWidget = QVideoWidget()
        
        # Set video output
        self.mediaPlayer.setVideoOutput(self.videoWidget)
        
        # Create layout for controls
        control_layout = QHBoxLayout()
        
        # Buttons and controls
        openBtn = QPushButton('Open Video')
        youtubeBtn = QPushButton('Open YouTube URL')
        self.listenBtn = QPushButton('🎤')  # Microphone emoji
        self.listenBtn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border-radius: 15px;
                padding: 5px;
                font-size: 20px;
            }
            QPushButton:pressed {
                background-color: #ff4444;
            }
        """)
        self.listenBtn.setFixedSize(40, 40)
        
        self.volumeSlider = QSlider(Qt.Horizontal)
        self.volumeSlider.setRange(0, 100)
        self.volumeSlider.setValue(20)
        
        # Volume icon and label
        volumeLabel = QLabel()
        volumeLabel.setPixmap(self.style().standardIcon(QStyle.SP_MediaVolume).pixmap(20, 20))
        
        # Connect controls
        openBtn.clicked.connect(self.open_file)
        youtubeBtn.clicked.connect(self.open_youtube_url)
        self.listenBtn.pressed.connect(self.start_listening)
        self.listenBtn.released.connect(self.stop_listening)
        self.volumeSlider.valueChanged.connect(self.set_volume)
        
        # Add widgets to control layout
        control_layout.addWidget(openBtn)
        control_layout.addWidget(youtubeBtn)
        control_layout.addWidget(self.listenBtn)
        control_layout.addWidget(volumeLabel)
        control_layout.addWidget(self.volumeSlider)
        
        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(self.videoWidget)
        layout.addLayout(control_layout)
        
        self.setLayout(layout)

    def start_listening(self):
        if self.listen_thread:
            # Store current volume and lower it
            self.original_volume = self.volumeSlider.value()
            self.volumeSlider.setValue(10)  # Lower to 10%
            self.mediaPlayer.setVolume(10)
            self.listen_thread.start_listening()

    def stop_listening(self):
        if self.listen_thread:
            # Restore original volume
            if hasattr(self, 'original_volume'):
                self.volumeSlider.setValue(self.original_volume)
                self.mediaPlayer.setVolume(self.original_volume)
            self.listen_thread.stop_listening()

    def handle_command(self, command):
        if 'take screenshot' in command:
            self.take_screenshot()
        elif 'make note' in command:
            self.make_note()
        elif 'pause video' in command or 'pause' in command:
            self.mediaPlayer.pause()
        elif 'play video' in command or 'play' in command:
            self.mediaPlayer.play()
        elif 'skip forward' in command:
            current_position = self.mediaPlayer.position()
            self.mediaPlayer.setPosition(current_position + 10000)
        elif 'skip backward' in command or 'go back' in command:
            current_position = self.mediaPlayer.position()
            self.mediaPlayer.setPosition(current_position - 10000)
        elif 'volume up' in command or 'increase volume' in command:
            current_volume = self.volumeSlider.value()
            new_volume = min(current_volume + 10, 100)
            self.volumeSlider.setValue(new_volume)
        elif 'volume down' in command or 'decrease volume' in command:
            current_volume = self.volumeSlider.value()
            new_volume = max(current_volume - 10, 0)
            self.volumeSlider.setValue(new_volume)
        elif 'mute' in command:
            self.mediaPlayer.setMuted(not self.mediaPlayer.isMuted())
        elif 'close video' in command or 'stop video' in command:
            self.close_video()

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Video")

        if filename != '':
            self.current_video_path = filename  # Store the video path
            self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(filename)))
            self.mediaPlayer.play()
    
    def open_youtube_url(self):
        url, ok = QInputDialog.getText(self, 'Open YouTube Video', 'Enter YouTube URL:')
        
        if ok and url:
            try:
                # Show loading message
                msg = QMessageBox()
                msg.setText("Downloading video... Please wait.")
                msg.setStandardButtons(QMessageBox.NoButton)
                msg.show()
                QApplication.processEvents()

                # Download YouTube video with additional options
                yt = YouTube(
                    url,
                    use_oauth=True,
                    allow_oauth_cache=True
                )
                
                # Try to get the highest quality stream
                streams = yt.streams.filter(progressive=True, file_extension='mp4')
                if not streams:
                    QMessageBox.warning(self, "Error", "No suitable video stream found")
                    msg.close()
                    return
                
                video_stream = streams.order_by('resolution').desc().first()
                
                # Create temp file with .mp4 extension
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4', dir=self.temp_dir)
                temp_file.close()
                
                try:
                    # Download to temp file
                    video_path = video_stream.download(
                        output_path=self.temp_dir,
                        filename=os.path.basename(temp_file.name)
                    )
                    
                    # Close loading message
                    msg.close()

                    # Play the downloaded video
                    self.current_video_path = video_path  # After successful download, store the video path
                    self.mediaPlayer.setMedia(QMediaContent(QUrl.fromLocalFile(video_path)))
                    self.mediaPlayer.play()
                    
                except Exception as download_error:
                    QMessageBox.warning(self, "Download Error", f"Failed to download video: {str(download_error)}")
                    msg.close()
                    if os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)

            except Exception as e:
                error_message = str(e)
                if "HTTP Error 400" in error_message:
                    error_message = "Invalid YouTube URL or video is unavailable"
                QMessageBox.warning(self, "Error", f"Error loading YouTube video: {error_message}")
                if 'msg' in locals():
                    msg.close()

    def take_screenshot(self):
        if not self.current_video_path:
            QMessageBox.warning(self, "Error", "No video is currently playing")
            return

        try:
            # Create screenshots directory in Obsidian vault
            videos_folder = os.path.join(PATH_TO_DIRECTORY, 'Videos')
            attachments_folder = os.path.join(videos_folder, 'attachments')
            os.makedirs(attachments_folder, exist_ok=True)

            # Open the video file
            cap = cv2.VideoCapture(self.current_video_path)
            if not cap.isOpened():
                QMessageBox.warning(self, "Error", "Could not capture video frame")
                return

            # Get current position in milliseconds
            current_pos = self.mediaPlayer.position()
            
            # Set video position
            cap.set(cv2.CAP_PROP_POS_MSEC, current_pos)
            
            # Read the frame
            ret, frame = cap.read()
            if ret:
                # Generate filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f'screenshot_{timestamp}.png'
                filepath = os.path.join(attachments_folder, filename)
                
                # Save the frame directly to attachments folder
                cv2.imwrite(filepath, frame)
                print(f"Screenshot saved as {filepath}")
                
                # Add to markdown
                self.save_screenshot_to_markdown(filename)
                
                # Show success message
                QMessageBox.information(
                    self,
                    "Success", 
                    f"Screenshot saved and linked in notes"
                )
            else:
                QMessageBox.warning(self, "Error", "Could not capture frame")

            # Release the video capture
            cap.release()

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error taking screenshot: {str(e)}")
    
    def make_note(self):
            # Pause the video
        self.mediaPlayer.pause()

    # Listen for dictation
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        with microphone as source:
            print("Listening for note...")
            audio = recognizer.listen(source)

        try:
            note_text = recognizer.recognize_google(audio)
            print(f"Note: {note_text}")
        # Save the note
            self.save_note_to_markdown(note_text)
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
    
    def save_note_to_markdown(self, note_text):
        video_name = os.path.basename(self.mediaPlayer.media().canonicalUrl().toString())
        video_title = os.path.splitext(video_name)[0]
        videos_folder = os.path.join(PATH_TO_DIRECTORY, 'Videos')
        os.makedirs(videos_folder, exist_ok=True)
        markdown_file = os.path.join(videos_folder, f"{video_title}.md")

    # Timestamp
        position = self.mediaPlayer.position()
        timestamp = int(position / 1000)

    # Format note entry
        note_entry = f"\n\n### Timestamp {timestamp}s\n{note_text}\n"

    # Save or append to the Markdown file
        with open(markdown_file, 'a', encoding='utf-8') as f:
            f.write(note_entry)

        print(f"Note saved to {markdown_file}")
        
    def save_screenshot_to_markdown(self, image_filename):
        video_name = os.path.basename(self.mediaPlayer.media().canonicalUrl().toString())
        video_title = os.path.splitext(video_name)[0]
        videos_folder = os.path.join(PATH_TO_DIRECTORY, 'Videos')
        os.makedirs(videos_folder, exist_ok=True)
        markdown_file = os.path.join(videos_folder, f"{video_title}.md")

    # Timestamp
        position = self.mediaPlayer.position()
        timestamp = int(position / 1000)

    # Assuming images are stored in 'Videos/attachments'
        attachments_folder = os.path.join(videos_folder, 'attachments')
        os.makedirs(attachments_folder, exist_ok=True)
        image_path = os.path.join(attachments_folder, image_filename)
    # Move or save the image to attachments folder

    # Markdown image syntax
        image_entry = f"\n\n### Screenshot at {timestamp}s\n![{image_filename}](attachments/{image_filename})\n"

    # Save or append to the Markdown file
        with open(markdown_file, 'a', encoding='utf-8') as f:
            f.write(image_entry)

        print(f"Screenshot embedded in {markdown_file}")

    def __del__(self):
        # Cleanup temporary files when the application closes
        try:
            for file in os.listdir(self.temp_dir):
                if file.endswith('.mp4'):
                    os.remove(os.path.join(self.temp_dir, file))
        except:
            pass

    def set_volume(self, value):
        # Keep playback volume low for better command recognition
        playback_volume = min(value, 20)  # Cap at 20% volume
        self.mediaPlayer.setVolume(playback_volume)

    def closeEvent(self, event):
        try:
            # Stop any playing video
            self.mediaPlayer.stop()
            self.mediaPlayer.setMedia(QMediaContent())
            
            # Stop the listening thread
            if self.listen_thread:
                self.listen_thread.stop()
                self.listen_thread.wait()
            
            # Accept the close event
            event.accept()
            
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
            event.accept()

    def close_video(self):
        try:
            # Stop the media player
            self.mediaPlayer.stop()
            self.mediaPlayer.setMedia(QMediaContent())
            
            # Clear the current video path
            self.current_video_path = None
            
            # Show success message
            QMessageBox.information(self, "Success", "Video closed successfully")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error closing video: {str(e)}")




if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoPlayer()
    window.show()
    sys.exit(app.exec_())
