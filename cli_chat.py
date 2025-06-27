#!/usr/bin/env python3
"""
CLI Chat Client for Obelisk FastAPI Server
Connects to the local FastAPI server with streaming responses.
"""

import asyncio
import json
import sys
from typing import Optional
import httpx
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner

console = Console()

class ChatClient:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.current_session_id: Optional[str] = None
    
    async def close(self):
        await self.client.aclose()
    
    async def send_message(self, message: str, stream: bool = True, use_session: bool = False) -> None:
        """Send a message to the chat API and handle the response"""
        
        payload = {
            "message": message,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        try:
            if use_session and self.current_session_id:
                if stream:
                    await self._handle_session_streaming_response(payload)
                else:
                    await self._handle_session_non_streaming_response(payload)
            else:
                if stream:
                    await self._handle_streaming_response(payload)
                else:
                    await self._handle_non_streaming_response(payload)
        except httpx.ConnectError:
            console.print("[red]❌ Error: Could not connect to the server at {}[/red]".format(self.base_url))
            console.print("[yellow]💡 Make sure the FastAPI server is running with: uv run python main.py[/yellow]")
        except httpx.TimeoutException:
            console.print("[red]❌ Error: Request timed out[/red]")
        except Exception as e:
            console.print(f"[red]❌ Error: {str(e)}[/red]")
    
    async def _handle_streaming_response(self, payload: dict) -> None:
        """Handle streaming response from the API"""
        
        response_content = ""
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/chat",
            json=payload,
            headers={"Accept": "text/event-stream"}
        ) as response:
            
            if response.status_code != 200:
                error_text = await response.aread()
                console.print(f"[red]❌ Server Error ({response.status_code}): {error_text.decode()}[/red]")
                return
            
            console.print("\n[bold blue]🤖 Assistant:[/bold blue]")
            
            with Live(console=console, refresh_per_second=10) as live:
                async for chunk in response.aiter_lines():
                    if chunk.startswith("data: "):
                        data = chunk[6:]  # Remove "data: " prefix
                        
                        if data.strip() == "[DONE]":
                            break
                        
                        try:
                            chunk_data = json.loads(data)
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    content = delta["content"]
                                    response_content += content
                                    
                                    # Update the live display with the current response
                                    if response_content.strip():
                                        live.update(Panel(
                                            Markdown(response_content),
                                            title="Response",
                                            border_style="blue"
                                        ))
                        except json.JSONDecodeError:
                            continue
        
        console.print()  # Add a newline after streaming is complete
    
    async def _handle_non_streaming_response(self, payload: dict) -> None:
        """Handle non-streaming response from the API"""
        
        with console.status("[bold green]Thinking...", spinner="dots"):
            response = await self.client.post(f"{self.base_url}/chat", json=payload)
        
        if response.status_code != 200:
            console.print(f"[red]❌ Server Error ({response.status_code}): {response.text}[/red]")
            return
        
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            console.print("\n[bold blue]🤖 Assistant:[/bold blue]")
            console.print(Panel(Markdown(content), title="Response", border_style="blue"))
        else:
            console.print("[yellow]⚠️ No response content received[/yellow]")
    
    async def _handle_session_streaming_response(self, payload: dict) -> None:
        """Handle streaming response from the session-based chat API"""
        
        response_content = ""
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/sessions/{self.current_session_id}/chat",
            json=payload,
            headers={"Accept": "text/event-stream"}
        ) as response:
            
            if response.status_code != 200:
                error_text = await response.aread()
                console.print(f"[red]❌ Server Error ({response.status_code}): {error_text.decode()}[/red]")
                return
            
            console.print("\n[bold blue]🤖 Assistant:[/bold blue]")
            
            with Live(console=console, refresh_per_second=10) as live:
                async for chunk in response.aiter_lines():
                    if chunk.startswith("data: "):
                        data = chunk[6:]  # Remove "data: " prefix
                        
                        if data.strip() == "[DONE]":
                            break
                        
                        try:
                            chunk_data = json.loads(data)
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    content = delta["content"]
                                    response_content += content
                                    
                                    # Update the live display with the current response
                                    if response_content.strip():
                                        live.update(Panel(
                                            Markdown(response_content),
                                            title="Response (Session Context)",
                                            border_style="blue"
                                        ))
                        except json.JSONDecodeError:
                            continue
        
        console.print()  # Add a newline after streaming is complete
    
    async def _handle_session_non_streaming_response(self, payload: dict) -> None:
        """Handle non-streaming response from the session-based chat API"""
        
        with console.status("[bold green]Thinking...", spinner="dots"):
            response = await self.client.post(f"{self.base_url}/sessions/{self.current_session_id}/chat", json=payload)
        
        if response.status_code != 200:
            console.print(f"[red]❌ Server Error ({response.status_code}): {response.text}[/red]")
            return
        
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            console.print("\n[bold blue]🤖 Assistant:[/bold blue]")
            console.print(Panel(Markdown(content), title="Response (Session Context)", border_style="blue"))
        else:
            console.print("[yellow]⚠️ No response content received[/yellow]")
    
    async def check_server_health(self) -> bool:
        """Check if the server is running and healthy"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False
    
    async def create_session(self) -> Optional[str]:
        """Create a new chat session and return session ID"""
        try:
            response = await self.client.post(f"{self.base_url}/sessions")
            if response.status_code == 200:
                data = response.json()
                return data["session_id"]
            else:
                console.print(f"[red]❌ Failed to create session: {response.status_code}[/red]")
                return None
        except Exception as e:
            console.print(f"[red]❌ Error creating session: {str(e)}[/red]")
            return None
    
    async def get_session_history(self, session_id: str) -> Optional[dict]:
        """Get the history of a session"""
        try:
            response = await self.client.get(f"{self.base_url}/sessions/{session_id}")
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            console.print(f"[red]❌ Error getting session history: {str(e)}[/red]")
            return None

@click.command()
@click.option("--server", default="http://localhost:8001", help="FastAPI server URL")
@click.option("--no-stream", is_flag=True, help="Disable streaming responses")
@click.option("--single-message", "-m", help="Send a single message and exit")
@click.option("--session", "-s", help="Use existing session ID")
@click.option("--new-session", is_flag=True, help="Create a new session")
@click.option("--show-history", is_flag=True, help="Show session history before chatting")
def main(server: str, no_stream: bool, single_message: Optional[str], session: Optional[str], new_session: bool, show_history: bool):
    """
    🚀 Obelisk CLI Chat Client
    
    A beautiful command-line interface for chatting with your FastAPI server.
    """
    
    # Print welcome banner
    session_info = ""
    if session:
        session_info = f"Session: [cyan]{session}[/cyan]\n"
    elif new_session:
        session_info = "Session: [yellow]Creating new...[/yellow]\n"
    
    console.print(Panel.fit(
        "[bold blue]🚀 Obelisk CLI Chat Client[/bold blue]\n"
        f"Connected to: [green]{server}[/green]\n"
        f"Streaming: [{'red]Disabled' if no_stream else 'green]Enabled'}[/green]\n"
        f"{session_info}",
        border_style="blue"
    ))
    
    async def run_chat():
        client = ChatClient(server)
        
        # Check server health
        console.print("\n[yellow]🔍 Checking server connection...[/yellow]")
        if not await client.check_server_health():
            console.print(f"[red]❌ Cannot connect to server at {server}[/red]")
            console.print("[yellow]💡 Make sure the FastAPI server is running with: uv run python main.py[/yellow]")
            await client.close()
            return
        
        console.print("[green]✅ Server is running![/green]")
        
        # Handle session management
        use_session = False
        if new_session or session:
            use_session = True
            
            if new_session:
                # Create a new session
                console.print("\n[yellow]🔄 Creating new session...[/yellow]")
                client.current_session_id = await client.create_session()
                if client.current_session_id:
                    console.print(f"[green]✅ New session created: {client.current_session_id}[/green]")
                else:
                    console.print("[red]❌ Failed to create session. Continuing without session.[/red]")
                    use_session = False
            elif session:
                # Use existing session
                client.current_session_id = session
                console.print(f"\n[yellow]🔍 Using session: {session}[/yellow]")
                
                # Validate session exists
                session_info = await client.get_session_history(session)
                if session_info:
                    console.print("[green]✅ Session found![/green]")
                    
                    if show_history and session_info["messages"]:
                        console.print("\n[bold cyan]📜 Session History:[/bold cyan]")
                        for msg in session_info["messages"]:
                            role_color = "green" if msg["role"] == "user" else "blue"
                            role_icon = "👤" if msg["role"] == "user" else "🤖"
                            console.print(f"[{role_color}]{role_icon} {msg['role'].title()}:[/{role_color}] {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")
                        console.print()
                else:
                    console.print(f"[yellow]⚠️ Session {session} not found. Continuing without session.[/yellow]")
                    use_session = False
                    client.current_session_id = None
        
        try:
            if single_message:
                # Single message mode
                console.print(f"\n[bold green]👤 You:[/bold green] {single_message}")
                await client.send_message(single_message, stream=not no_stream, use_session=use_session)
            else:
                # Interactive chat mode
                console.print("\n[bold green]💬 Interactive Chat Mode[/bold green]")
                console.print("[dim]Type your message and press Enter. Type 'quit', 'exit', or 'bye' to exit.[/dim]")
                
                while True:
                    try:
                        # Get user input with a pretty prompt
                        user_input = Prompt.ask("\n[bold green]👤 You")
                        
                        if user_input.lower().strip() in ['quit', 'exit', 'bye', 'q']:
                            console.print("\n[yellow]👋 Goodbye![/yellow]")
                            break
                        
                        if not user_input.strip():
                            console.print("[dim]Please enter a message.[/dim]")
                            continue
                        
                        # Send message to the API
                        await client.send_message(user_input, stream=not no_stream, use_session=use_session)
                        
                    except KeyboardInterrupt:
                        console.print("\n\n[yellow]👋 Chat interrupted. Goodbye![/yellow]")
                        break
                    except EOFError:
                        console.print("\n\n[yellow]👋 Goodbye![/yellow]")
                        break
        
        finally:
            await client.close()
    
    # Run the async chat function
    try:
        asyncio.run(run_chat())
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Goodbye![/yellow]")
        sys.exit(0)

if __name__ == "__main__":
    main() 