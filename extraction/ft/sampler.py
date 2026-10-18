"""Run extraction through Tinker (base model or your fine-tuned one). Same return shape as
extract.extract(): (Page, seconds). Used by evaluate.py and by the Django backend.

PRIVACY: this sends the page photo to Tinker's cloud. The app only uses it when you opt in.
"""
import time
from functools import lru_cache

from ftcommon import BASE_MODEL, load_model_info, load_pil, parse_page, user_message


class TinkerExtractionError(Exception):
    def __init__(self, message: str, raw: str = ""):
        super().__init__(message)
        self.raw = raw


@lru_cache(maxsize=4)
def _client(model_path: str | None, base_model: str):
    import tinker
    from tinker_cookbook import model_info, renderers
    from tinker_cookbook.image_processing_utils import get_image_processor
    from tinker_cookbook.tokenizer_utils import get_tokenizer

    service = tinker.ServiceClient()
    sampler = (service.create_sampling_client(model_path=model_path) if model_path
               else service.create_sampling_client(base_model=base_model))
    renderer = renderers.get_renderer(model_info.get_recommended_renderer_name(base_model),
                                      get_tokenizer(base_model), get_image_processor(base_model))
    return sampler, renderer


def extract(image_path: str, finetuned: bool = True, extra_rules=None, max_tokens: int = 4096):
    """Returns (Page, seconds). finetuned=False uses the untouched base model (the baseline)."""
    import tinker
    if finetuned:
        info = load_model_info()
        model_path, base = info["model_path"], info["base_model"]
    else:
        model_path, base = None, BASE_MODEL
    sampler, renderer = _client(model_path, base)
    prompt = renderer.build_generation_prompt([user_message(load_pil(image_path), extra_rules)])
    params = tinker.SamplingParams(max_tokens=max_tokens, temperature=0.0,
                                   stop=renderer.get_stop_sequences())
    start = time.perf_counter()
    result = sampler.sample(prompt, num_samples=1, sampling_params=params).result()
    seconds = time.perf_counter() - start
    message, _ = renderer.parse_response(result.sequences[0].tokens)
    from tinker_cookbook.renderers import get_text_content
    raw = get_text_content(message)
    try:
        return parse_page(raw), seconds
    except Exception as e:
        raise TinkerExtractionError(f"Model output did not match schema: {e}", raw)
