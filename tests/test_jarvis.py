import datetime as dt
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jarvis
from memory import MemoryStore


class SilentSpeech:
    def __init__(self):
        self.spoken = []

    def say(self, text):
        self.spoken.append(text)


class JarvisTests(unittest.TestCase):
    def setUp(self):
        self.speech = SilentSpeech()
        self.config = jarvis.DEFAULTS.copy()
        self.assistant = jarvis.JarvisAssistant(self.config, speech=self.speech, chat=None)

    def test_builtin_command_requires_wake_word(self):
        self.assertIsNone(self.assistant.handle_text("what time is it"))
        self.assertEqual(self.assistant.handle_text("Jarvis, what time is it?").count(":"), 1)

    def test_voice_chat_turn_does_not_require_wake_word(self):
        response = self.assistant.handle_text("what time is it", require_wake=False)
        self.assertIsNotNone(response)
        self.assertIn("It is", response)

    def test_speech_output_notifies_voice_ui(self):
        spoken = []
        speech = jarvis.SpeechOutput(enabled=False, on_speak=spoken.append)
        speech.say("Voice reply")
        self.assertEqual(spoken, ["Voice reply"])

    def test_wake_word_alone_awaits_next_utterance(self):
        self.assertEqual(self.assistant.handle_text("Jarvis"), "Yes?")
        self.assistant.handle_text("help")
        self.assertIn("what I can do", self.speech.spoken[-1])

    def test_help_identity_and_date(self):
        self.assertIn("offline-first", self.assistant.execute("who are you"))
        self.assertIn("calculator", self.assistant.execute("help"))
        self.assertIn(str(dt.datetime.now().year), self.assistant.execute("what is the date"))

    def test_unknown_without_local_chat_is_safe(self):
        answer = self.assistant.execute("do a complex task")
        self.assertIn("local chat model", answer)

    def test_stop_command_sets_exit_flag(self):
        self.assistant.execute("stop")
        self.assertTrue(self.assistant.stop_requested)

    def test_chat_model_is_loaded_in_process_only_when_used(self):
        with tempfile.TemporaryDirectory() as folder:
            model_path = Path(folder) / "fake.gguf"
            model_path.write_bytes(b"local-test-model")
            calls = []

            class FakeLlama:
                def __init__(self, **kwargs):
                    calls.append(("init", kwargs))

                def create_chat_completion(self, **kwargs):
                    calls.append(("chat", {"messages": [dict(item) for item in kwargs["messages"]]}))
                    return {"choices": [{"message": {"content": "Hello locally."}}]}

            module = types.ModuleType("llama_cpp")
            module.Llama = FakeLlama
            chat = jarvis.LocalChat(model_path, history_turns=2, threads=3)
            chat.set_memory_provider(lambda _query: "[Earlier / user] I like Mars")
            self.assertEqual(calls, [])
            with patch.dict(sys.modules, {"llama_cpp": module}):
                self.assertEqual(chat.ask("Hello"), "Hello locally.")
            self.assertEqual(calls[0][0], "init")
            self.assertEqual(calls[0][1]["n_threads"], 3)
            self.assertEqual(calls[1][0], "chat")
            self.assertIn("I like Mars", calls[1][1]["messages"][-1]["content"])

    def test_chat_model_missing_fails_gracefully(self):
        chat = jarvis.LocalChat(Path("definitely-not-a-model.gguf"))
        with self.assertRaisesRegex(RuntimeError, "Local model file not found"):
            chat.ask("Hello")

    def test_chat_is_disabled_by_default(self):
        self.assertFalse(jarvis.DEFAULTS["use_local_chat"])
        self.assertNotIn("ollama_url", jarvis.DEFAULTS)

    def test_conversation_memory_survives_store_reopen_and_finds_topic(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "memory.sqlite3"
            store = MemoryStore(database)
            session_id = store.list_sessions()[0]["id"]
            store.save_exchange(session_id, "My favorite planet is Mars", "I'll remember that you like Mars.")
            reopened = MemoryStore(database)
            transcript = reopened.messages(session_id)
            self.assertEqual([entry["role"] for entry in transcript], ["user", "assistant"])
            self.assertIn("Mars", reopened.relevant_context("what did I tell you about Mars?"))
            self.assertEqual(len(reopened.search_messages("Mars")), 2)

    def test_assistant_persists_builtin_exchanges_to_local_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            store = MemoryStore(Path(folder) / "memory.sqlite3")
            session_id = store.list_sessions()[0]["id"]
            self.assistant.bind_memory(store, session_id)
            self.assistant.execute("who are you")
            messages = store.messages(session_id)
            self.assertEqual(messages[0]["role"], "user")
            self.assertEqual(messages[0]["content"], "who are you")
            self.assertEqual(messages[1]["role"], "assistant")

    def test_assistant_can_answer_a_saved_memory_question_without_chat_model(self):
        with tempfile.TemporaryDirectory() as folder:
            store = MemoryStore(Path(folder) / "memory.sqlite3")
            session_id = store.list_sessions()[0]["id"]
            store.save_exchange(session_id, "I am planning a trip to Iceland", "I hope you have a wonderful trip.")
            self.assistant.bind_memory(store, session_id)
            answer = self.assistant.execute("what did I say about Iceland before?")
            self.assertIn("Iceland", answer)
            self.assertIn("planning a trip", answer)


if __name__ == "__main__":
    unittest.main()
