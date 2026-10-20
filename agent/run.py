"""Run a single analyst request with an ephemeral ADK session."""
import argparse
import asyncio
from google.adk.runners import InMemoryRunner
from google.adk.agents.run_config import RunConfig
from google.genai import types
from cascade_analyst.agent import root_agent


async def run(prompt):
    runner = InMemoryRunner(agent=root_agent, app_name="cascade_analyst")
    session = await runner.session_service.create_session(app_name="cascade_analyst", user_id="officer")
    calls, successful = [], []
    try:
        async with asyncio.timeout(240):
            async for event in runner.run_async(user_id="officer", session_id=session.id,
                    new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
                    run_config=RunConfig(max_llm_calls=8)):
                for call in event.get_function_calls():
                    calls.append(call.name)
                    print(f"TOOL {call.name}", flush=True)
                for response in event.get_function_responses():
                    if response.response.get("status") == "ok":
                        successful.append(response.name)
                if event.is_final_response() and event.content:
                    print("\n".join(p.text for p in event.content.parts if p.text), flush=True)
        return {"calls": calls, "successful_tools": successful}
    finally:
        await runner.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--verify-tools", action="store_true")
    args = parser.parse_args()
    evidence = asyncio.run(run(args.prompt))
    if args.verify_tools:
        assert "search_businesses" in evidence["successful_tools"], evidence
        assert "analyze_cascade" in evidence["successful_tools"], evidence
        print("LIVE_AGENT_VERIFIED")
