#!/usr/bin/env python3
"""
Quick test script for RAG system
"""
import requests
import json
import sys

BASE_URL = "http://localhost:5001"

def test_health():
    """Test RAG system health"""
    try:
        response = requests.get(f"{BASE_URL}/api/rag/health")
        data = response.json()
        print("🔍 Health Check:")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {json.dumps(data, indent=2)}")
        return data.get('ready', False)
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_providers():
    """Test available providers"""
    try:
        response = requests.get(f"{BASE_URL}/api/rag/providers")
        data = response.json()
        print("\n🔧 Available Providers:")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {json.dumps(data, indent=2)}")
        return data.get('providers', {})
    except Exception as e:
        print(f"❌ Providers check failed: {e}")
        return {}

def test_search(query="What are the main requirements?", provider="openai", model="gpt-3.5-turbo"):
    """Test RAG search"""
    try:
        payload = {
            "question": query,
            "provider": provider,
            "model": model
        }
        
        print(f"\n🤖 Testing RAG Query:")
        print(f"  Query: {query}")
        print(f"  Provider: {provider}")
        print(f"  Model: {model}")
        
        response = requests.post(f"{BASE_URL}/api/rag/query", 
                               json=payload,
                               timeout=30)
        
        data = response.json()
        print(f"  Status: {response.status_code}")
        
        if data.get('success'):
            print(f"  ✅ Answer: {data['answer'][:200]}...")
            print(f"  📚 Sources: {len(data.get('sources', []))} found")
            
            if data.get('sources'):
                for i, source in enumerate(data['sources'][:2]):  # Show first 2 sources
                    print(f"    Source {i+1}: {source.get('content', '')[:100]}...")
        else:
            print(f"  ❌ Error: {data.get('error')}")
            
        return data.get('success', False)
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        return False

def main():
    print("🚀 Testing RAG System\n" + "="*50)
    
    # Test health
    healthy = test_health()
    if not healthy:
        print("\n❌ System not healthy - check API keys and setup")
        sys.exit(1)
    
    # Test providers
    providers = test_providers()
    if not providers:
        print("\n❌ No providers available")
        sys.exit(1)
    
    # Test with first available provider
    available_provider = list(providers.keys())[0]
    available_models = providers[available_provider]
    model = available_models[0] if available_models else "gpt-3.5-turbo"
    
    # Test different queries
    test_queries = [
        "What is this document about?",
        "What are the main requirements?", 
        "Can you summarize the key points?",
        "What are the tender specifications?"
    ]
    
    success_count = 0
    for query in test_queries:
        success = test_search(query, available_provider, model)
        if success:
            success_count += 1
    
    print(f"\n{'='*50}")
    print(f"🎯 Test Results: {success_count}/{len(test_queries)} successful")
    
    if success_count == len(test_queries):
        print("✅ All tests passed! RAG system is working correctly.")
        print(f"\n🌐 Access the chat interface at: {BASE_URL}/chat")
    else:
        print("⚠️  Some tests failed. Check the errors above.")

if __name__ == "__main__":
    main()