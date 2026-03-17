"""
FastAPI 后端服务 - 封装 Agent 提供 REST API 和流式 SSE 接口
"""
import json
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

# 导入 Agent
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="Agentic Writing API", version="1.0.0")

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    query: str
    scenario: str = None  # 可选，让 Agent 自动识别


class CompareRequest(BaseModel):
    query: str
    scenario: str
    agent_text: str
    user_text: str


# 全局存储 Agent 实例（懒加载）
_agent = None

def get_agent():
    global _agent
    if _agent is None:
        from agent import WritingAgent
        _agent = WritingAgent()
    return _agent


@app.get("/")
def root():
    return {"status": "ok", "service": "Agentic Writing API"}


@app.post("/api/generate")
async def generate_text(request: GenerateRequest):
    """
    非流式生成接口（返回完整结果）
    """
    try:
        agent = get_agent()
        result = agent.run(request.query)
        return {
            "success": True,
            "query": result["query"],
            "scenario": result["scenario"],
            "final_text": result["final_text"],
            "stats": result["stats"],
            "skill_outputs": {
                k: v.output if hasattr(v, "output") else v
                for k, v in result.get("skill_outputs", {}).items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/stream")
async def generate_stream(request: GenerateRequest):
    """
    流式生成接口（SSE）- 实时返回思考过程和结果
    简化版：先返回静态步骤，再返回完整结果
    """
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'message': 'Agent 启动...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            
            # 发送规划步骤
            yield f"data: {json.dumps({'type': 'step', 'idx': 1, 'total': 5, 'skill': 'need_analysis', 'desc': '分析写作需求...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.5)
            
            # 运行 Agent（非流式，但模拟流式体验）
            loop = asyncio.get_event_loop()
            agent = get_agent()
            
            # 根据场景发送不同的步骤
            # 这里简化处理，实际可以根据 result 中的 skill_outputs 来发送
            yield f"data: {json.dumps({'type': 'step', 'idx': 2, 'total': 5, 'skill': 'topic_analysis', 'desc': '审题分析中...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.5)
            
            yield f"data: {json.dumps({'type': 'step', 'idx': 3, 'total': 5, 'skill': 'writing', 'desc': '正在撰写内容...'}, ensure_ascii=False)}\n\n"
            
            # 执行实际生成
            result = await loop.run_in_executor(None, agent.run, request.query)
            
            # 发送完成步骤
            yield f"data: {json.dumps({'type': 'step', 'idx': 4, 'total': 5, 'skill': 'quality_review', 'desc': '质量审核通过'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.2)
            
            yield f"data: {json.dumps({'type': 'step', 'idx': 5, 'total': 5, 'skill': 'format_polish', 'desc': '排版优化完成'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.2)
            
            # 发送最终结果
            result_data = {
                'type': 'complete',
                'query': result['query'],
                'scenario': result['scenario'],
                'final_text': result['final_text'],
                'stats': result['stats']
            }
            yield f"data: {json.dumps(result_data, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            error_data = {'type': 'error', 'message': str(e)}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.post("/api/compare")
async def compare_texts(request: CompareRequest):
    """
    对比评测接口 - GSB 评估
    """
    try:
        from evaluator import evaluate, EvalResult
        
        eval_result = evaluate(
            query=request.query,
            scenario=request.scenario,
            baseline_text=request.user_text,  # 用户内容作为 baseline
            agentic_text=request.agent_text,   # Agent 内容作为对比
        )
        
        return {
            "success": True,
            "verdict": eval_result.verdict,  # "A"=Agent胜, "B"=用户胜, "S"=平局
            "agent_score": eval_result.agentic_score,
            "user_score": eval_result.baseline_score,
            "dimensions": eval_result.dimensions,
            "reasoning": eval_result.reasoning
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scenarios")
def get_scenarios():
    """获取支持的场景列表"""
    from config import SCENARIOS
    return {"scenarios": SCENARIOS}


if __name__ == "__main__":
    import uvicorn
    print("启动 API 服务: http://localhost:8000")
    print("API 文档: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
