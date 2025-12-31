"""
OpenAI SDK implementation for image generation
"""
import logging
import base64
import os
import re
import time
import requests
from io import BytesIO
from typing import Optional, List
from openai import OpenAI
from PIL import Image
from .base import ImageProvider
from config import get_config

logger = logging.getLogger(__name__)

# Image download settings
# 注意: TUN 模式透明代理可能导致下载速度波动,使用较长的超时时间
IMAGE_DOWNLOAD_TIMEOUT = 180  # seconds (adjusted for TUN mode transparency proxy)
IMAGE_DOWNLOAD_MAX_RETRIES = 5  # 增加重试次数以应对网络波动
IMAGE_DOWNLOAD_RETRY_DELAY = 3  # seconds between retries


def _get_image_download_proxy() -> Optional[dict]:
    """
    Get HTTP proxy configuration for image downloads from environment

    Environment Variables:
        IMAGE_DOWNLOAD_PROXY: HTTP/HTTPS proxy URL (e.g., http://proxy:8080)

    Returns:
        Proxy dict for requests or None if not configured
    """
    proxy_url = os.getenv('IMAGE_DOWNLOAD_PROXY')
    if proxy_url:
        logger.info(f"Using proxy for image downloads: {proxy_url}")
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    return None


def download_image_with_retry(url: str, timeout: int = IMAGE_DOWNLOAD_TIMEOUT,
                              max_retries: int = IMAGE_DOWNLOAD_MAX_RETRIES) -> Optional[Image.Image]:
    """
    Download image from URL with retry mechanism and optional proxy support

    Args:
        url: Image URL to download
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts

    Returns:
        PIL Image object or None if failed
    """
    last_error = None
    proxies = _get_image_download_proxy()

    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading image (attempt {attempt + 1}/{max_retries}): {url[:80]}...")
            response = requests.get(url, timeout=timeout, stream=True, proxies=proxies)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            image.load()  # Ensure image is fully loaded
            logger.info(f"Successfully downloaded image: {image.size}, {image.mode}")
            return image
        except Exception as e:
            last_error = e
            logger.warning(f"Download attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(IMAGE_DOWNLOAD_RETRY_DELAY)

    logger.error(f"Failed to download image after {max_retries} attempts: {last_error}")
    return None


class OpenAIImageProvider(ImageProvider):
    """Image generation using OpenAI SDK (compatible with Gemini via proxy)"""
    
    def __init__(self, api_key: str, api_base: str = None, model: str = "gemini-3-pro-image-preview"):
        """
        Initialize OpenAI image provider
        
        Args:
            api_key: API key
            api_base: API base URL (e.g., https://aihubmix.com/v1)
            model: Model name to use
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=get_config().OPENAI_IMAGE_TIMEOUT,  # 图像生成超时（默认90秒）
            max_retries=get_config().OPENAI_IMAGE_MAX_RETRIES  # 图像生成重试次数（默认3次）
        )
        self.model = model
    
    def _encode_image_to_base64(self, image: Image.Image) -> str:
        """
        Encode PIL Image to base64 string
        
        Args:
            image: PIL Image object
            
        Returns:
            Base64 encoded string
        """
        buffered = BytesIO()
        # Convert to RGB if necessary (e.g., RGBA images)
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        image.save(buffered, format="JPEG", quality=95)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    def generate_image(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K"
    ) -> Optional[Image.Image]:
        """
        Generate image using OpenAI SDK
        
        Note: OpenAI format does NOT support 4K images, defaults to 1K
        
        Args:
            prompt: The image generation prompt
            ref_images: Optional list of reference images
            aspect_ratio: Image aspect ratio
            resolution: Image resolution (only 1K supported, parameter ignored)
            
        Returns:
            Generated PIL Image object, or None if failed
        """
        try:
            # Build message content
            content = []
            
            # Add reference images first (if any)
            if ref_images:
                for ref_img in ref_images:
                    base64_image = self._encode_image_to_base64(ref_img)
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    })
            
            # Add text prompt
            content.append({"type": "text", "text": prompt})
            
            logger.debug(f"Calling OpenAI API for image generation with {len(ref_images) if ref_images else 0} reference images...")
            logger.debug(f"Config - aspect_ratio: {aspect_ratio} (resolution ignored, OpenAI format only supports 1K)")
            
            # Note: resolution is not supported in OpenAI format, only aspect_ratio via system message
            # Try with modalities first (for OpenAI-compatible APIs)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": f"aspect_ratio={aspect_ratio}"},
                        {"role": "user", "content": content},
                    ],
                    modalities=["text", "image"]
                )
            except Exception as modalities_error:
                logger.warning(f"Failed with modalities parameter: {modalities_error}, trying without...")
                # Fallback: try without modalities parameter (some APIs don't support it)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": f"aspect_ratio={aspect_ratio}"},
                        {"role": "user", "content": content},
                    ]
                )
            
            logger.debug("OpenAI API call completed")
            
            # Extract image from response - handle different response formats
            message = response.choices[0].message
            
            # OpenRouter returns images in model_extra['images'] (not in standard content field)
            if hasattr(message, 'model_extra') and message.model_extra and 'images' in message.model_extra:
                images_data = message.model_extra['images']
                logger.debug(f"Found images in model_extra: {len(images_data) if isinstance(images_data, list) else 'N/A'} items")
                
                if isinstance(images_data, list) and len(images_data) > 0:
                    # Extract image from the first item
                    first_image = images_data[0]
                    
                    # Handle different image formats
                    if isinstance(first_image, str):
                        # Direct string: base64 data URL or HTTP URL
                        if first_image.startswith('data:image'):
                            base64_data = first_image.split(',', 1)[1]
                            image_data = base64.b64decode(base64_data)
                            image = Image.open(BytesIO(image_data))
                            logger.debug(f"Successfully extracted image from base64 data URL: {image.size}, {image.mode}")
                            return image
                        elif first_image.startswith('http://') or first_image.startswith('https://'):
                            image = download_image_with_retry(first_image)
                            if image:
                                logger.debug(f"Successfully downloaded image from URL: {image.size}, {image.mode}")
                                return image
                    elif isinstance(first_image, dict):
                        # OpenRouter format: {'type': 'image_url', 'image_url': {'url': 'data:image/...'}}
                        # Check for image_url format (OpenRouter standard)
                        if 'image_url' in first_image:
                            image_url_obj = first_image['image_url']
                            if isinstance(image_url_obj, dict) and 'url' in image_url_obj:
                                image_url = image_url_obj['url']
                                
                                if image_url.startswith('data:image'):
                                    # Base64 data URL
                                    base64_data = image_url.split(',', 1)[1]
                                    image_data = base64.b64decode(base64_data)
                                    image = Image.open(BytesIO(image_data))
                                    logger.debug(f"Successfully extracted image from image_url base64: {image.size}, {image.mode}")
                                    return image
                                elif image_url.startswith('http://') or image_url.startswith('https://'):
                                    # HTTP URL - download it with retry
                                    image = download_image_with_retry(image_url)
                                    if image:
                                        logger.debug(f"Successfully downloaded image from image_url: {image.size}, {image.mode}")
                                        return image
                        
                        # Fallback: Check for direct 'url' key
                        if 'url' in first_image:
                            image_url = first_image['url']
                            if image_url.startswith('data:image'):
                                base64_data = image_url.split(',', 1)[1]
                                image_data = base64.b64decode(base64_data)
                                image = Image.open(BytesIO(image_data))
                                logger.debug(f"Successfully extracted image from direct url base64: {image.size}, {image.mode}")
                                return image
                            elif image_url.startswith('http://') or image_url.startswith('https://'):
                                image = download_image_with_retry(image_url)
                                if image:
                                    logger.debug(f"Successfully downloaded image from direct url: {image.size}, {image.mode}")
                                    return image
                        
                        # Fallback: Check for 'data' key
                        elif 'data' in first_image:
                            base64_data = first_image['data']
                            if isinstance(base64_data, str):
                                if base64_data.startswith('data:image'):
                                    base64_data = base64_data.split(',', 1)[1]
                                image_data = base64.b64decode(base64_data)
                                image = Image.open(BytesIO(image_data))
                                logger.debug(f"Successfully extracted image from dict data: {image.size}, {image.mode}")
                                return image
            
            # Try multi_mod_content first (custom format from some proxies)
            if hasattr(message, 'multi_mod_content') and message.multi_mod_content:
                parts = message.multi_mod_content
                for part in parts:
                    if "text" in part:
                        logger.debug(f"Response text: {part['text'][:100] if len(part['text']) > 100 else part['text']}")
                    if "inline_data" in part:
                        image_data = base64.b64decode(part["inline_data"]["data"])
                        image = Image.open(BytesIO(image_data))
                        logger.debug(f"Successfully extracted image: {image.size}, {image.mode}")
                        return image
            
            # Check for refusal or error messages
            if hasattr(message, 'refusal') and message.refusal:
                logger.warning(f"API returned refusal: {message.refusal}")
            
            # Check for tool_calls (some APIs use this)
            if hasattr(message, 'tool_calls') and message.tool_calls:
                logger.info(f"Found tool_calls: {len(message.tool_calls)} items")
                for tool_call in message.tool_calls:
                    logger.info(f"Tool call: {tool_call}")
            
            # Try standard OpenAI content format (list of content parts)
            if hasattr(message, 'content') and message.content:
                # If content is a list (multimodal response)
                if isinstance(message.content, list):
                    for part in message.content:
                        if isinstance(part, dict):
                            # Handle image_url type
                            if part.get('type') == 'image_url':
                                image_url = part.get('image_url', {}).get('url', '')
                                if image_url.startswith('data:image'):
                                    # Extract base64 data from data URL
                                    base64_data = image_url.split(',', 1)[1]
                                    image_data = base64.b64decode(base64_data)
                                    image = Image.open(BytesIO(image_data))
                                    logger.debug(f"Successfully extracted image from content: {image.size}, {image.mode}")
                                    return image
                            # Handle text type
                            elif part.get('type') == 'text':
                                text = part.get('text', '')
                                if text:
                                    logger.debug(f"Response text: {text[:100] if len(text) > 100 else text}")
                        elif hasattr(part, 'type'):
                            # Handle as object with attributes
                            if part.type == 'image_url':
                                image_url = getattr(part, 'image_url', {})
                                if isinstance(image_url, dict):
                                    url = image_url.get('url', '')
                                else:
                                    url = getattr(image_url, 'url', '')
                                if url.startswith('data:image'):
                                    base64_data = url.split(',', 1)[1]
                                    image_data = base64.b64decode(base64_data)
                                    image = Image.open(BytesIO(image_data))
                                    logger.debug(f"Successfully extracted image from content object: {image.size}, {image.mode}")
                                    return image
                # If content is a string, try to extract image from it
                elif isinstance(message.content, str):
                    content_str = message.content
                    logger.debug(f"Response content (string): {content_str[:200] if len(content_str) > 200 else content_str}")

                    # Try to extract Markdown base64 image first: ![...](data:image/...;base64,...)
                    # This is faster than URL download, so check it first
                    markdown_base64_pattern = r'!\[.*?\]\((data:image/[^;]+;base64,([A-Za-z0-9+/=]+))\)'
                    markdown_base64_matches = re.findall(markdown_base64_pattern, content_str)
                    if markdown_base64_matches:
                        base64_data = markdown_base64_matches[0][1]  # Get the base64 part
                        logger.debug(f"Found Markdown base64 image (length: {len(base64_data)})")
                        try:
                            image_data = base64.b64decode(base64_data)
                            image = Image.open(BytesIO(image_data))
                            logger.debug(f"Successfully extracted Markdown base64 image: {image.size}, {image.mode}")
                            return image
                        except Exception as decode_error:
                            logger.warning(f"Failed to decode Markdown base64 image: {decode_error}")

                    # Try to extract Markdown image URL: ![...](url)
                    markdown_pattern = r'!\[.*?\]\((https?://[^\s\)]+)\)'
                    markdown_matches = re.findall(markdown_pattern, content_str)
                    if markdown_matches:
                        image_url = markdown_matches[0]  # Use the first image URL found
                        logger.debug(f"Found Markdown image URL: {image_url}")
                        image = download_image_with_retry(image_url)
                        if image:
                            logger.debug(f"Successfully downloaded image from Markdown URL: {image.size}, {image.mode}")
                            return image
                        else:
                            logger.warning(f"Failed to download image from Markdown URL after retries: {image_url}")
                    
                    # Try to extract plain URL (not in Markdown format)
                    url_pattern = r'(https?://[^\s\)\]]+\.(?:png|jpg|jpeg|gif|webp|bmp)(?:\?[^\s\)\]]*)?)'
                    url_matches = re.findall(url_pattern, content_str, re.IGNORECASE)
                    if url_matches:
                        image_url = url_matches[0]
                        logger.debug(f"Found plain image URL: {image_url}")
                        image = download_image_with_retry(image_url)
                        if image:
                            logger.debug(f"Successfully downloaded image from plain URL: {image.size}, {image.mode}")
                            return image
                        else:
                            logger.warning(f"Failed to download image from plain URL after retries: {image_url}")
                    
                    # Try to extract base64 data URL from string
                    base64_pattern = r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)'
                    base64_matches = re.findall(base64_pattern, content_str)
                    if base64_matches:
                        base64_data = base64_matches[0]
                        logger.debug(f"Found base64 image data in string")
                        try:
                            image_data = base64.b64decode(base64_data)
                            image = Image.open(BytesIO(image_data))
                            logger.debug(f"Successfully extracted base64 image from string: {image.size}, {image.mode}")
                            return image
                        except Exception as decode_error:
                            logger.warning(f"Failed to decode base64 image from string: {decode_error}")
            
            # Log error details
            logger.warning(f"Unable to extract image. Message type: {type(message)}")
            logger.warning(f"Message content type: {type(getattr(message, 'content', None))}")
            logger.warning(f"Message content: {repr(getattr(message, 'content', 'N/A'))}")
            
            raise ValueError("No valid multimodal response received from OpenAI API")
            
        except Exception as e:
            error_detail = f"Error generating image with OpenAI (model={self.model}): {type(e).__name__}: {str(e)}"
            logger.error(error_detail, exc_info=True)
            raise Exception(error_detail) from e
