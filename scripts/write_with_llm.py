"""
ES: Redacta explicaciones con el LLM (Qwen) por API. Se ejecuta en cualquier máquina (sin Colab ni GPU
propia); el servidor solo sirve el resultado. Recuperación -> LLM -> validador de cifras y citas; si
falla dos veces se usa la plantilla determinista. Guarda tras cada sitio y puede reanudarse.
Uso:
  export LLM_BASE_URL=https://.../v1 LLM_API_KEY=... MODEL_LLM=Qwen/Qwen3-8B
  python scripts/write_with_llm.py [--web] [--resume] [--retriever bm25|hybrid]
  python scripts/write_with_llm.py --candidates m1.json     # candidatos de M1 (dict id -> objeto con SHAP)
  python scripts/write_with_llm.py --backend local          # modelo local con transformers (necesita GPU)
Web: con --web usa la caché (data/rag/web_cache.json); versionadla y desplegad con WEB_CACHE_ONLY=1.


"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.explanations.index import TextIndex  # noqa: E402
from app.explanations.llm import DEFAULT_MODEL, ApiGenerator  # noqa: E402
from app.explanations.retrieval import build_retriever  # noqa: E402
from app.explanations.writer import (  # noqa: E402,F401  (re-exported for tests / reexportado para pruebas)
    EXPLAIN_PROMPT,
    build_messages,
    candidate_template,
    site_input,
    web_query_for,
    write_explanation,
)


class LocalGenerator:
    """
    ES: LLM abierto cargado localmente (4 bits por defecto). Solo con --backend local.
    EN: Open LLM loaded locally (4-bit by default). Only with --backend local.
    """

    def __init__(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        model_id = os.getenv("MODEL_LLM", DEFAULT_MODEL)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        quantization = (
            BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
            if os.getenv("USE_4BIT", "1") == "1"
            else None
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, device_map="auto", quantization_config=quantization, dtype=torch.float16
        )

    def __call__(self, data: dict, fragments: list[dict], reminder: str = "") -> str:
        from app.explanations.llm import strip_thinking

        inputs = self.tokenizer.apply_chat_template(
            build_messages(data, fragments, reminder),
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,  # ES: versiones nuevas pueden devolver un dict / EN: newer versions may return a dict
            enable_thinking=False,
        ).to(self.model.device)
        output = self.model.generate(**inputs, max_new_tokens=400, do_sample=False)
        new_tokens = output[0][inputs["input_ids"].shape[1] :]
        return strip_thinking(self.tokenizer.decode(new_tokens, skip_special_tokens=True))


def main(argv: list[str] | None = None, retriever=None, generator=None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--web", action="store_true", help="añade resultados de internet / adds web results")
    parser.add_argument("--candidates", help="JSON {id: objeto} de M1 / M1 candidates JSON")
    parser.add_argument(
        "--resume", action="store_true", help="salta lo ya redactado / skip what is already written"
    )
    parser.add_argument("--retriever", choices=["bm25", "hybrid"], default=os.getenv("RETRIEVER", "hybrid"))
    parser.add_argument("--backend", choices=["api", "local"], default="api")
    args = parser.parse_args(argv)
    retriever = retriever or build_retriever(args.retriever, TextIndex())
    generator = generator or (LocalGenerator() if args.backend == "local" else ApiGenerator())

    if args.candidates:
        source = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
        output_path = Path("data/rag/explained_candidates.json")
        items = {
            key: (
                obj,
                f"{obj.get('nombre', key)} candidato análogo límites",
                candidate_template(key, obj),
                None,
            )
            for key, obj in source.items()
        }
    else:
        output_path = Path("data/rag/explanations.json")
        source = json.loads(output_path.read_text(encoding="utf-8"))
        items = {key: (*site_input(obj), web_query_for(obj)) for key, obj in source.items()}
    if args.resume and output_path.exists():  # ES: continuar donde se quedó / EN: continue where it stopped
        previous = json.loads(output_path.read_text(encoding="utf-8"))
        for key in source:
            if "texto_origen" in previous.get(key, {}):
                source[key] = previous[key]

    for number, (key, (data, query, template, web_query)) in enumerate(items.items(), 1):
        if args.resume and "texto_origen" in source[key]:
            print(f"[{number}/{len(items)}] {key}: ya redactado / already written")
            continue
        source[key].update(
            write_explanation(data, query, retriever, generator, template, args.web, web_query=web_query)
        )
        # ES: guardado atómico tras CADA sitio / EN: atomic save after EVERY site
        tmp = output_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(source, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, output_path)
        print(f"[{number}/{len(items)}] {key}: {source[key]['texto_origen']}")


if __name__ == "__main__":
    main()
