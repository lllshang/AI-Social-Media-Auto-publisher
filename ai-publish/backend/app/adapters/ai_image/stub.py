from app.adapters.base import ImageGenerateInput, ImageGenerateResult
from app.adapters.factory import get_adapter_factory


class StubImageAdapter:
    provider = "stub"

    async def generate(self, data: ImageGenerateInput) -> ImageGenerateResult:
        prompt = data.topic
        storage = get_adapter_factory().get_storage_adapter()
        placeholder = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
            b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        paths = []
        for _ in range(max(1, data.count)):
            file_path, _ = storage.save_bytes(placeholder, suffix=".png")
            paths.append(file_path)
        return ImageGenerateResult(image_paths=paths, provider=self.provider, prompt=prompt, cost=0.0)
