import time
from pathlib import Path
from fastapi import FastAPI
from just_agents.llm_session import LLMSession
from starlette.responses import StreamingResponse
from dotenv import load_dotenv
from just_agents.utils import RotateKeys
from fastapi.middleware.cors import CORSMiddleware
import loguru
# import litellm
# litellm.set_verbose=True
log_path = Path(__file__)
log_path = Path(log_path.parent, "logs", "symptom_checker.log")
loguru.logger.add(log_path.absolute(), rotation="10 MB")


load_dotenv(override=True)
# What is the influence of different alleles in rs10937739 and what is MTOR gene?
app = FastAPI(title="Symptom Checker API endpoint.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", description="Defalt message", response_model=str)
async def default():
    return "This is default page for Symptom Checker API endpoint."

@app.post("/symptom_checker/chat/completions")
async def chat_completions(request: dict):
    try:
        loguru.logger.debug(request)
        curent_llm: dict = {"model": request["model"], "temperature": request.get("temperature", 0)}
        if request["model"].startswith("groq/"):
            curent_llm["key_getter"] = RotateKeys("./groq_keys.txt")

        prompt_path = "data"
        tools = None

        if request["model"].startswith("groq/llama-3.1"):
            prompt_path = Path(prompt_path, "groq_lama3_prompt.txt")
        if request["model"].startswith("gpt-4o"):
            prompt_path = Path(prompt_path, "gpt4o_prompt.txt")

        if prompt_path:
            with open(prompt_path) as f:
                if (len(request["messages"]) > 0) and (request["messages"][0]["role"] == "system"):
                    request["messages"][0]["content"] = f.read()
                else:
                    request["messages"].insert(0, {"role":"system", "content":f.read()})


        session: LLMSession = LLMSession(
            llm_options=curent_llm,
            tools = tools
        )
        if request["messages"]:
            if request.get("stream") and str(request.get("stream")).lower() != "false":
                return StreamingResponse(
                    session.stream_all(request["messages"], run_callbacks=False), media_type="application/x-ndjson"
                )
            resp_content = session.query_add_all(request["messages"], run_callbacks=False)
        else:
            resp_content = "Something goes wrong, request did not contain messages!!!"
    except Exception as e:
        loguru.logger.error(str(e))
        resp_content = str(e)

    return {
        "id": "1",
        "object": "chat.completion",
        "created": time.time(),
        "model": curent_llm["model"],
        "choices": [{"message": {"role":"assistant", "content":resp_content}}],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8089)