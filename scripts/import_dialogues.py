import os
import json
import uuid
from datetime import datetime, timezone

def import_dialogues(dialogues_path: str = "dialogues", output_path: str = "model_artifacts/training_data.jsonl"):
    """Scan a directory of dialogue files and produce a JSONL training dataset.

    Expected file format: plain‑text where each conversation is separated by a line
    containing only `---`.  Within a conversation, user and assistant messages are on
    separate lines prefixed with `User:` and `Assistant:`.  If the prefixes are missing
    the function will infer alternating roles.
    """
    base_dir = os.path.abspath(os.path.join(os.getcwd(), dialogues_path))
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Dialogues directory not found: {base_dir}")

    output_file = os.path.abspath(os.path.join(os.getcwd(), output_path))
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as out_f:
        for root, _, files in os.walk(base_dir):
            for filename in files:
                if not filename.lower().endswith(".txt"):
                    continue
                file_path = os.path.join(root, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    raw = f.read()
                conversations = [c.strip() for c in raw.split("---") if c.strip()]
                for conv in conversations:
                    lines = [l.strip() for l in conv.splitlines() if l.strip()]
                    role = "user"
                    for line in lines:
                        if line.lower().startswith("assistant:"):
                            role = "assistant"
                            content = line[len("assistant:"):].strip()
                        elif line.lower().startswith("user:"):
                            role = "user"
                            content = line[len("user:"):].strip()
                        else:
                            content = line
                        entry = {
                            "conversation_id": str(uuid.uuid4()),
                            "role": role,
                            "message": content,
                            "language": "en",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        out_f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"Training data written to {output_file}")

if __name__ == "__main__":
    import_dialogues(dialogues_path="data/dialogues")
