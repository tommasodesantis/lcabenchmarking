import json
import requests
import aiohttp
import openai
import asyncio
from typing import List, Dict, Any, AsyncGenerator
from r2r import R2RClient
from prompts import RETRIEVAL_PROMPT, WEB_SEARCH_PROMPT, MERGER_PROMPT

class LCAAnalyzer:
    def __init__(self, r2r_api_key: str, requesty_api_key: str, openrouter_api_key: str):
        self.r2r_api_key = r2r_api_key
        self.requesty_api_key = requesty_api_key
        self.openrouter_api_key = openrouter_api_key
        self.client = R2RClient("https://api.cloud.sciphi.ai")
        
        self.retrieval_prompt = RETRIEVAL_PROMPT
        self.web_search_prompt = WEB_SEARCH_PROMPT
        self.merger_prompt = MERGER_PROMPT

    def get_chunks(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            response = self.client.retrieval.search(
                query=query,
                search_settings={
                    "limit": limit
                }
            )
            
            # Access the chunk_search_results through the results attribute
            chunks = response.results.chunk_search_results
            
            # Convert chunks to list of dictionaries for consistent usage
            formatted_chunks = []
            for chunk in chunks:
                formatted_chunk = {
                    "text": chunk.text,
                    "score": chunk.score,
                    "metadata": chunk.metadata
                }
                formatted_chunks.append(formatted_chunk)
                
            return formatted_chunks
            
        except Exception as e:
            raise

    def parse_sse_chunk(self, chunk: bytes) -> str:
        """Parse a chunk of SSE data and extract the content."""
        if not chunk:
            return ""
        
        try:
            data = json.loads(chunk.decode('utf-8').split('data: ')[1])
            if data.get('choices') and len(data['choices']) > 0:
                delta = data['choices'][0].get('delta', {})
                return delta.get('content', '')
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
        return ""

    async def process_with_llm(self, query: str, context: str, model: str, system_prompt: str, use_streaming: bool = True) -> AsyncGenerator[str, None]:
        client = openai.OpenAI(
            base_url="https://router.requesty.ai/v1",
            api_key=self.requesty_api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/yourusername/yourrepo",
                "X-Title": "LCA Analysis Tool"
            }
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {query}\n\nContext: {context}"}
        ]

        try:
            if use_streaming:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    top_p=0,
                    stream=True
                )
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    top_p=0,
                    stream=False
                )
                yield response.choices[0].message.content
        except Exception as e:
            print(f"LLM error: {str(e)}")
            raise

    async def web_search(self, query: str) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8888",
            "X-Title": "LCA Analysis Tool"
        }
        
        messages = [
            {"role": "system", "content": self.web_search_prompt},
            {"role": "user", "content": f"Query: {query}\n\nContext: Please search the web for relevant LCA and environmental metrics data."}
        ]

        async def attempt_stream(model: str) -> AsyncGenerator[str, None]:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0,
                "top_p": 0,
                "stream": True
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload
                    ) as response:
                        first_chunk_received = False
                        try:
                            async with asyncio.timeout(45):  # 45 second timeout for first chunk
                                async for line in response.content:
                                    if line:
                                        content = self.parse_sse_chunk(line)
                                        if content:
                                            first_chunk_received = True
                                            yield content
                                            # After first chunk, continue without timeout
                                            async for next_line in response.content:
                                                if next_line:
                                                    next_content = self.parse_sse_chunk(next_line)
                                                    if next_content:
                                                        yield next_content
                        except asyncio.TimeoutError:
                            if not first_chunk_received and model == "perplexity/sonar-reasoning":
                                print(f"Timeout with {model}, falling back to perplexity/sonar")
                                async for chunk in attempt_stream("perplexity/sonar"):
                                    yield chunk
                            else:
                                # If we timeout with fallback model or after first chunk, try non-streaming
                                raise
            except Exception as e:
                print(f"Web search streaming error with {model}: {str(e)}")
                # Fallback to non-streaming request
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={**payload, "stream": False}
                )
                result = response.json()
                yield result["choices"][0]["message"]["content"]

        # Start with primary model
        async for chunk in attempt_stream("perplexity/sonar-reasoning"):
            yield chunk

    async def analyze(self, query: str, include_web_search: bool = False) -> AsyncGenerator[Dict[str, str], None]:
        try:
            chunks = self.get_chunks(query)
            context = "\n\n".join([chunk["text"] for chunk in chunks])
            
            if not include_web_search:
                db_stream = self.process_with_llm(
                    query=query,
                    context=context,
                    model="cline/o3-mini",
                    system_prompt=self.retrieval_prompt,
                    use_streaming=True
                )
                async for chunk in db_stream:
                    yield {"section": "database", "content": chunk}
            else:
                # Create placeholders for accumulated results
                db_result = ""
                web_result = ""
                
                # Process database search
                db_stream = self.process_with_llm(
                    query=query,
                    context=context,
                    model="cline/o3-mini",
                    system_prompt=self.retrieval_prompt,
                    use_streaming=True
                )
                async for chunk in db_stream:
                    db_result += chunk
                    yield {"section": "database", "content": chunk}

                # Process web search
                web_stream = self.web_search(query)
                async for chunk in web_stream:
                    web_result += chunk
                    yield {"section": "web", "content": chunk}
                
                # Generate comparison table only after web search is complete
                merged_context = f"""User Query:\n{query}\n\nDatabase Results:\n{db_result}\n\nWeb Search Results:\n{web_result}"""
                table_stream = self.process_with_llm(
                    query=query,
                    context=merged_context,
                    model="google/gemini-2.0-flash-001",
                    system_prompt=self.merger_prompt,
                    use_streaming=True
                )
                async for chunk in table_stream:
                    yield {"section": "table", "content": chunk}
        except Exception as e:
            print(f"Analysis error: {str(e)}")
            raise
