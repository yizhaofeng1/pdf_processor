"""Abstract Base Class for Vision Model Providers."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
import base64
from pathlib import Path
import httpx

from ..models.ai_result import VisionAnalysisRequest, VisionAnalysisResult


def encode_image_base64(image_path: str | Path) -> str:
    """Encode an image file to a base64 string."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    return base64.b64encode(path.read_bytes()).decode("utf-8")


class VisionModelProvider(ABC):
    """Abstract interface defining vision-language model integration."""

    def __init__(
        self,
        provider_id: str,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout: float = 60.0,
        proxy: Optional[str] = None,
    ) -> None:
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.proxy = proxy or None

    def create_http_client(self) -> httpx.Client:
        """Create an httpx client configured with timeout and optional proxy."""
        proxy_url = None
        if self.proxy and self.proxy.strip():
            raw_p = self.proxy.strip()
            if not raw_p.startswith(("http://", "https://", "socks5://", "socks5h://")):
                raw_p = f"http://{raw_p}"
            proxy_url = raw_p

        return httpx.Client(
            proxy=proxy_url,
            timeout=self.timeout,
            follow_redirects=True,
        )

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """Test API reachability, key validity, and model response.

        Returns:
            (success: bool, message: str)
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_available_models(self) -> list[str]:
        """Fetch list of supported model IDs from the provider endpoint."""
        raise NotImplementedError

    @abstractmethod
    def analyze_pages(self, request: VisionAnalysisRequest) -> VisionAnalysisResult:
        """Analyze page images and return structured question boundaries."""
        raise NotImplementedError
