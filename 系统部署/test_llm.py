"""
测试 LLM 连接
"""
import sys
sys.path.insert(0, '/Volumes/增元/项目/douyin/系统部署')

from services.llm import get_llm_service

def test_llm():
    print("正在测试 LLM 连接...")
    
    service = get_llm_service()
    print(f"Provider: {service.provider}")
    print(f"Model: {service.model}")
    print(f"Base URL: {service.base_url}")
    
    # 列出可用模型
    print("\n可用模型:")
    models = service.list_models()
    for m in models:
        print(f"  - {m.get('name')}")
    
    # 测试对话
    print("\n测试对话:")
    messages = [
        {"role": "user", "content": "你好，请用一句话介绍自己"}
    ]
    
    response = service.chat(messages)
    print(f"回复: {response}")
    
    if response:
        print("\n✅ LLM 连接成功!")
    else:
        print("\n❌ LLM 连接失败")

if __name__ == "__main__":
    test_llm()
