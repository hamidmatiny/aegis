import { useEffect, useRef, useState, type FormEvent } from "react";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  busy?: boolean;
  placeholder?: string;
  onListeningChange?: (listening: boolean) => void;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
};

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** True when the free-text looks like a sign-out request (client intent; no backend NLP). */
export function isSignOutIntent(text: string): boolean {
  const t = text.trim().toLowerCase().replace(/[.!?]+$/g, "");
  return /^(please\s+)?(sign|log)\s*(me\s*)?out$/.test(t) || t === "sign me out";
}

export function AssistantComposer({
  value,
  onChange,
  onSubmit,
  busy = false,
  placeholder = 'Ask about your stack, or say "sign me out"…',
  onListeningChange,
}: Props) {
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const speechSupported = typeof window !== "undefined" && Boolean(getSpeechRecognition());

  useEffect(() => {
    onListeningChange?.(listening);
  }, [listening, onListeningChange]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
    };
  }, []);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!value.trim() || busy) return;
    onSubmit();
  }

  function toggleMic() {
    const Ctor = getSpeechRecognition();
    if (!Ctor) return;
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      setListening(false);
      return;
    }
    const recognition = new Ctor();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript ?? "";
      if (transcript) onChange(transcript);
    };
    recognition.onerror = () => setListening(false);
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    setListening(true);
    recognition.start();
  }

  return (
    <form className="assistant-composer" onSubmit={handleSubmit}>
      <button
        type="button"
        className="icon-btn"
        title="File upload isn’t available yet — paste details into your question instead"
        aria-label="Attach file (not available yet)"
        disabled
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
        </svg>
      </button>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={busy}
        aria-label="Ask AEGIS"
      />
      <button
        type="button"
        className={`icon-btn mic${listening ? " active" : ""}`}
        title={
          speechSupported
            ? listening
              ? "Stop listening"
              : "Talk — dictation fills the question box (browser speech recognition)"
            : "Voice dictation isn’t supported in this browser"
        }
        aria-label="Talk"
        aria-pressed={listening}
        disabled={!speechSupported || busy}
        onClick={toggleMic}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
          <path d="M19 10v2a7 7 0 01-14 0v-2M12 19v4" />
        </svg>
      </button>
      <button
        type="submit"
        className="icon-btn send"
        title="Send"
        aria-label="Send"
        disabled={busy || !value.trim()}
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
      </button>
    </form>
  );
}
