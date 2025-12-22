#!/usr/bin/env python3
"""
测试图片生成功能
用于验证 OpenRouter 配置是否正确
"""
import sys
import os
from pathlib import Path

# 添加 backend 目录到路径
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# 设置 Flask 应用上下文
os.environ['FLASK_APP'] = 'backend.app'

def test_image_provider():
    """测试图片提供者配置"""
    print("=" * 60)
    print("测试图片生成配置")
    print("=" * 60)
    
    try:
        from backend.app import create_app
        from backend.services.ai_providers import get_image_provider, get_provider_format, _get_provider_config
        
        app = create_app()
        
        with app.app_context():
            # 检查配置
            print("\n1. 检查 Provider Format:")
            format_type = get_provider_format()
            print(f"   Provider Format: {format_type}")
            
            print("\n2. 检查 Provider 配置:")
            provider_format, api_key, api_base = _get_provider_config()
            print(f"   Format: {provider_format}")
            print(f"   API Base: {api_base}")
            print(f"   API Key: {'***' + api_key[-4:] if api_key and len(api_key) > 4 else 'None'}")
            
            print("\n3. 创建图片提供者:")
            image_provider = get_image_provider(model='google/gemini-3-pro-image-preview')
            print(f"   Provider Type: {type(image_provider).__name__}")
            print(f"   Model: {image_provider.model}")
            
            if hasattr(image_provider.client, 'base_url'):
                print(f"   Client Base URL: {image_provider.client.base_url}")
            elif hasattr(image_provider.client, '_client'):
                # OpenAI SDK
                base_url = getattr(image_provider.client._client, 'base_url', 'N/A')
                print(f"   Client Base URL: {base_url}")
            
            print("\n✅ 配置验证成功！")
            print("\n现在可以尝试在前端生成图片，应该会使用 OpenRouter API。")
            
    except Exception as e:
        print(f"\n❌ 错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_image_provider()
    sys.exit(0 if success else 1)

