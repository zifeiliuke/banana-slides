#!/usr/bin/env python3
"""
测试 API 连接脚本
用于验证 OpenRouter 配置是否正确
"""
import os
import sys
from pathlib import Path

# 添加 backend 目录到路径
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

def test_gemini_format():
    """测试 Gemini 格式的 API 调用"""
    print("=" * 60)
    print("测试 Gemini 格式 (Google GenAI SDK)")
    print("=" * 60)
    
    from google import genai
    from google.genai import types
    
    api_key = os.getenv('GOOGLE_API_KEY')
    api_base = os.getenv('GOOGLE_API_BASE', 'https://openrouter.ai/api/v1')
    model = os.getenv('IMAGE_MODEL', 'gemini-3-pro-image-preview')
    
    print(f"API Key: {'***' + api_key[-4:] if api_key and len(api_key) > 4 else 'None'}")
    print(f"API Base: {api_base}")
    print(f"Model: {model}")
    print()
    
    if not api_key:
        print("❌ GOOGLE_API_KEY 未设置")
        return False
    
    try:
        print("正在初始化 GenAI Client...")
        client = genai.Client(
            http_options=types.HttpOptions(base_url=api_base) if api_base else None,
            api_key=api_key
        )
        print("✅ Client 初始化成功")
        
        print("\n正在测试文本生成...")
        response = client.models.generate_content(
            model=model,
            contents="Hello, this is a test.",
            config=types.GenerateContentConfig(),
        )
        print(f"✅ 文本生成成功: {response.text[:100]}...")
        return True
        
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_openai_format():
    """测试 OpenAI 格式的 API 调用"""
    print("\n" + "=" * 60)
    print("测试 OpenAI 格式 (OpenAI SDK)")
    print("=" * 60)
    
    from openai import OpenAI
    
    api_key = os.getenv('OPENAI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    api_base = os.getenv('OPENAI_API_BASE', 'https://openrouter.ai/api/v1')
    model = os.getenv('IMAGE_MODEL', 'google/gemini-2.0-flash-exp')
    
    print(f"API Key: {'***' + api_key[-4:] if api_key and len(api_key) > 4 else 'None'}")
    print(f"API Base: {api_base}")
    print(f"Model: {model}")
    print()
    
    if not api_key:
        print("❌ OPENAI_API_KEY 或 GOOGLE_API_KEY 未设置")
        return False
    
    try:
        print("正在初始化 OpenAI Client...")
        client = OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        print("✅ Client 初始化成功")
        
        print("\n正在测试文本生成...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Hello, this is a test."}
            ]
        )
        print(f"✅ 文本生成成功: {response.choices[0].message.content[:100]}...")
        return True
        
    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n🔍 开始测试 API 连接...\n")
    
    # 从 .env 文件加载环境变量
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print(f"📄 从 {env_file} 加载环境变量...")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ[key] = value
        print("✅ 环境变量加载完成\n")
    else:
        print(f"⚠️  未找到 .env 文件: {env_file}\n")
    
    # 检查配置
    provider_format = os.getenv('AI_PROVIDER_FORMAT', 'gemini').lower()
    print(f"📋 AI_PROVIDER_FORMAT: {provider_format}\n")
    
    # 根据格式测试
    if provider_format == 'openai':
        success = test_openai_format()
    else:
        success = test_gemini_format()
        if not success:
            print("\n⚠️  Gemini 格式测试失败，尝试 OpenAI 格式...")
            success = test_openai_format()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 测试通过！API 配置正确。")
    else:
        print("❌ 测试失败！请检查配置。")
        print("\n💡 建议：")
        print("1. 确认 API Key 是否正确")
        print("2. 确认 API Base URL 是否正确")
        print("3. 如果使用 OpenRouter，建议设置 AI_PROVIDER_FORMAT=openai")
        print("4. OpenRouter 的 API Base URL 应该是: https://openrouter.ai/api/v1")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()

