"""
Audio & Video recording coordinator for Blackboard sessions.
Uses in-page Web Audio / WebRTC interception to record lecture audio cleanly,
along with Playwright's native tab video recording.
"""

import base64
import logging
from pathlib import Path
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger("agent.recorder")

# JavaScript injected into Blackboard Collaborate to intercept all WebRTC and HTML5 audio streams
AUDIO_CAPTURE_INIT_SCRIPT = """
(() => {
    if (window.__audioRecorderInitialized) return;
    window.__audioRecorderInitialized = true;

    window.__audioContext = null;
    window.__audioDestination = null;
    window.__mediaRecorder = null;
    window.__audioChunks = [];
    window.__capturedStreams = new Set();
    window.__connectedNodes = new WeakSet();

    function initAudioContext() {
        if (!window.__audioContext) {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (AudioCtx) {
                window.__audioContext = new AudioCtx();
                window.__audioDestination = window.__audioContext.createMediaStreamDestination();
                console.log('[BB-Recorder] AudioContext and Destination created.');
            }
        }
    }

    function hookAudioStream(stream) {
        try {
            if (!stream || !stream.getAudioTracks || stream.getAudioTracks().length === 0) return;
            if (window.__capturedStreams.has(stream.id)) return;
            window.__capturedStreams.add(stream.id);

            initAudioContext();
            if (!window.__audioContext || !window.__audioDestination) return;

            const source = window.__audioContext.createMediaStreamSource(stream);
            source.connect(window.__audioDestination);
            console.log('[BB-Recorder] Hooked incoming audio stream:', stream.id);

            // Also resume audio context if suspended
            if (window.__audioContext.state === 'suspended') {
                window.__audioContext.resume();
            }

            // Ensure recorder is started if not already
            if (!window.__mediaRecorder && window.__audioDestination.stream.getAudioTracks().length > 0) {
                startMediaRecorder();
            }
        } catch (e) {
            console.warn('[BB-Recorder] Error hooking stream:', e);
        }
    }

    function startMediaRecorder() {
        if (window.__mediaRecorder || !window.__audioDestination) return;
        try {
            const destStream = window.__audioDestination.stream;
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : (MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '');
            
            window.__mediaRecorder = new MediaRecorder(destStream, mimeType ? { mimeType } : {});
            window.__audioChunks = [];

            window.__mediaRecorder.ondataavailable = async (e) => {
                if (e.data && e.data.size > 0) {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        const base64data = reader.result.split(',')[1];
                        if (window.__onAudioChunk) {
                            window.__onAudioChunk(base64data);
                        } else {
                            window.__audioChunks.push(base64data);
                        }
                    };
                    reader.readAsDataURL(e.data);
                }
            };

            // Request slice every 2 seconds
            window.__mediaRecorder.start(2000);
            console.log('[BB-Recorder] MediaRecorder started with mimeType:', mimeType);
        } catch (err) {
            console.error('[BB-Recorder] Could not start MediaRecorder:', err);
        }
    }

    // 1. Intercept RTCPeerConnection ontrack
    const origRTCPeerConnection = window.RTCPeerConnection;
    if (origRTCPeerConnection) {
        window.RTCPeerConnection = function(...args) {
            const pc = new origRTCPeerConnection(...args);
            pc.addEventListener('track', (event) => {
                if (event.track && event.track.kind === 'audio') {
                    if (event.streams && event.streams[0]) {
                        hookAudioStream(event.streams[0]);
                    } else {
                        const s = new MediaStream([event.track]);
                        hookAudioStream(s);
                    }
                }
            });
            return pc;
        };
        window.RTCPeerConnection.prototype = origRTCPeerConnection.prototype;
    }

    // 2. Intercept HTMLAudioElement and HTMLVideoElement playback
    const origPlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function() {
        try {
            if (this.srcObject instanceof MediaStream) {
                hookAudioStream(this.srcObject);
            } else if (this.src && !window.__connectedNodes.has(this)) {
                initAudioContext();
                if (window.__audioContext && window.__audioDestination) {
                    try {
                        const source = window.__audioContext.createMediaElementSource(this);
                        source.connect(window.__audioDestination);
                        source.connect(window.__audioContext.destination);
                        window.__connectedNodes.add(this);
                    } catch(err) {
                        // ignore cross-origin media element errors
                    }
                }
            }
        } catch(e) {}
        return origPlay.apply(this, arguments);
    };

    // 3. Global controls exposed to Playwright
    window.__bbStartRecording = () => {
        initAudioContext();
        if (window.__audioDestination && !window.__mediaRecorder) {
            startMediaRecorder();
        }
    };

    window.__bbStopRecording = () => {
        return new Promise((resolve) => {
            if (!window.__mediaRecorder || window.__mediaRecorder.state === 'inactive') {
                resolve(window.__audioChunks || []);
                return;
            }
            window.__mediaRecorder.onstop = () => {
                resolve(window.__audioChunks || []);
            };
            window.__mediaRecorder.stop();
            console.log('[BB-Recorder] MediaRecorder stopped.');
        });
    };
})();
"""

class AudioRecorder:
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.chunks_received = 0
        self._file_handle = None
        self._is_recording = False

    async def attach_to_page(self, page: Page):
        """Expose Python callback to page and inject audio capture script."""
        self._file_handle = open(self.output_path, "wb")
        self._is_recording = True

        async def _handle_chunk(base64_data: str):
            if self._is_recording and self._file_handle and base64_data:
                try:
                    raw_bytes = base64.b64decode(base64_data)
                    self._file_handle.write(raw_bytes)
                    self._file_handle.flush()
                    self.chunks_received += 1
                except Exception as e:
                    logger.error(f"Failed to write audio chunk: {e}")

        # Expose binding for continuous streaming chunks
        try:
            await page.expose_binding("__onAudioChunk", lambda source, data: _handle_chunk(data))
        except Exception:
            # Might already be exposed
            pass

        # Inject the script on every navigation and immediately
        await page.add_init_script(AUDIO_CAPTURE_INIT_SCRIPT)
        try:
            await page.evaluate(AUDIO_CAPTURE_INIT_SCRIPT)
        except Exception:
            pass

        logger.info(f"Attached AudioRecorder to page. Output: {self.output_path}")

    async def start(self, page: Page):
        """Signal the page recorder to start capturing audio."""
        try:
            await page.evaluate("window.__bbStartRecording && window.__bbStartRecording();")
            logger.info("Triggered in-page audio recording.")
        except Exception as e:
            logger.warning(f"Could not trigger __bbStartRecording: {e}")

    async def stop(self, page: Optional[Page] = None) -> Path:
        """Stop recording and flush remaining audio data."""
        self._is_recording = False
        if page:
            try:
                remaining_chunks = await page.evaluate(
                    "window.__bbStopRecording ? window.__bbStopRecording() : []"
                )
                if isinstance(remaining_chunks, list) and self._file_handle:
                    for chunk in remaining_chunks:
                        if chunk:
                            self._file_handle.write(base64.b64decode(chunk))
                    self._file_handle.flush()
            except Exception as e:
                logger.warning(f"Error stopping in-page recording: {e}")

        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

        logger.info(f"Audio recording completed. File size: {self.output_path.stat().st_size if self.output_path.exists() else 0} bytes")
        return self.output_path
