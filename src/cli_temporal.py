#!/usr/bin/env python3
"""
Temporal-based CLI Chat Client for Obelisk
Uses Temporal workflows instead of direct API calls
"""
import asyncio
import uuid
import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.prompt import Prompt
from datetime import datetime
from typing import Optional

from temporalio.client import Client

from src.config.settings import settings
from src.temporal.client import temporal_client
from src.temporal.workflows.simple_chat import SimpleChatWorkflow, SimpleStreamingChatWorkflow
from src.database.manager import db_manager
from src.models.chat import ChatSessionCreate

console = Console()


class TemporalChatClient:
    """CLI client that uses Temporal workflows for chat operations"""
    
    def __init__(self):
        self.temporal_client: Optional[Client] = None
        
    async def connect(self):
        """Connect to Temporal server"""
        try:
            self.temporal_client = await temporal_client.connect()
            console.print("✅ Connected to Temporal server", style="green")
        except Exception as e:
            console.print(f"❌ Failed to connect to Temporal: {e}", style="red")
            raise
    
    async def create_session(self) -> str:
        """Create a new chat session via database"""
        session = await db_manager.create_session(ChatSessionCreate())
        console.print(f"📝 Created new session: {session.id}", style="blue")
        return session.id
    
    async def show_session_history(self, session_id: str):
        """Display session history"""
        try:
            messages = await db_manager.get_session_history(session_id, offset=0, limit=50)
            
            if not messages:
                console.print("No messages in this session yet.", style="yellow")
                return
                
            console.print(f"\n📚 Session History ({len(messages)} messages):")
            console.print("="*60)
            
            for msg in messages:
                # Handle potentially None timestamp
                if msg.timestamp:
                    timestamp = msg.timestamp.strftime("%H:%M:%S")
                else:
                    timestamp = "N/A"
                    
                role_color = "blue" if msg.role.value == "user" else "green"
                role_emoji = "👤" if msg.role.value == "user" else "🤖"
                
                header = f"{role_emoji} {msg.role.value.upper()} [{timestamp}]"
                console.print(f"\n{header}", style=f"bold {role_color}")
                
                # Display content with proper formatting
                if msg.role.value == "assistant":
                    console.print(Markdown(msg.content))
                else:
                    console.print(msg.content, style="white")
                    
        except Exception as e:
            console.print(f"❌ Error fetching history: {e}", style="red")
    
    async def send_message_via_temporal(self, session_id: str, message: str, streaming: bool = True) -> str:
        """Send message using Temporal workflow"""
        if not self.temporal_client:
            raise Exception("Not connected to Temporal server")
        
        try:
            # Generate unique workflow ID
            workflow_id = f"chat-{session_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
            
            if streaming:
                # Use streaming workflow
                workflow_handle = await self.temporal_client.start_workflow(
                    SimpleStreamingChatWorkflow.run,
                    args=[session_id, message],
                    id=workflow_id,
                    task_queue=settings.temporal.task_queue,
                )
            else:
                # Use regular workflow
                workflow_handle = await self.temporal_client.start_workflow(
                    SimpleChatWorkflow.run,
                    args=[session_id, message, streaming],
                    id=workflow_id,
                    task_queue=settings.temporal.task_queue,
                )
            
            console.print(f"🔄 Started workflow: {workflow_id}", style="dim blue")
            
            # Wait for workflow completion
            result = await workflow_handle.result()
            
            return result.get("content", "No response received")
            
        except Exception as e:
            console.print(f"❌ Temporal workflow error: {e}", style="red")
            return f"Error processing message: {e}"
    
    async def interactive_chat(self, session_id: str, streaming: bool = True):
        """Interactive chat mode using Temporal workflows"""
        console.print("\n🚀 Starting Temporal-based Interactive Chat", style="bold green")
        console.print("Type 'quit', 'exit', or press Ctrl+C to end the conversation\n")
        
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("You", default="")
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    console.print("👋 Goodbye!", style="yellow")
                    break
                
                if not user_input.strip():
                    continue
                
                # Show thinking indicator
                with console.status("[bold blue]🤔 Processing via Temporal...", spinner="dots"):
                    response = await self.send_message_via_temporal(session_id, user_input, streaming)
                
                # Display response
                console.print("\n🤖 Assistant:", style="bold green")
                if response:
                    console.print(Markdown(response))
                else:
                    console.print("No response received.", style="yellow")
                console.print()
                
            except KeyboardInterrupt:
                console.print("\n👋 Chat ended by user", style="yellow")
                break
            except Exception as e:
                console.print(f"\n❌ Error: {e}", style="red")
    
    async def send_single_message(self, session_id: str, message: str, streaming: bool = True):
        """Send a single message and get response"""
        with console.status("[bold blue]🤔 Processing via Temporal...", spinner="dots"):
            response = await self.send_message_via_temporal(session_id, message, streaming)
        
        # Display the message exchange
        console.print(Panel(message, title="👤 Your Message", border_style="blue"))
        
        if response:
            console.print(Panel(Markdown(response), title="🤖 Assistant Response", border_style="green"))
        else:
            console.print(Panel("No response received", title="🤖 Assistant Response", border_style="yellow"))


@click.command()
@click.option('--server-url', default=None, help='Temporal server URL (default: from config)')
@click.option('--session', default=None, help='Use existing session ID')
@click.option('--new-session', is_flag=True, help='Create a new session')
@click.option('--show-history', is_flag=True, help='Show session history before chatting')
@click.option('--message', '-m', default=None, help='Send a single message and exit')
@click.option('--no-streaming', is_flag=True, help='Disable streaming responses')
@click.option('--task-queue', default=None, help='Temporal task queue (default: from config)')
def main(server_url, session, new_session, show_history, message, no_streaming, task_queue):
    """
    Temporal-based CLI Chat Client for Obelisk
    
    This version uses Temporal workflows instead of direct API calls.
    """
    async def run_client():
        # Update settings if provided
        if server_url:
            settings.temporal.server_url = server_url
        if task_queue:
            settings.temporal.task_queue = task_queue
        
        streaming = not no_streaming
        
        # Initialize client
        client = TemporalChatClient()
        
        try:
            # Connect to Temporal
            await client.connect()
            
            # Initialize database
            await db_manager.init_database()
            
            # Handle session
            session_id = session
            
            if new_session or not session_id:
                session_id = await client.create_session()
            
            # Show session info
            console.print(f"📋 Using session: {session_id}", style="cyan")
            
            # Show history if requested
            if show_history and session_id:
                await client.show_session_history(session_id)
            
            # Handle single message or interactive mode
            if message:
                await client.send_single_message(session_id, message, streaming)
            else:
                await client.interactive_chat(session_id, streaming)
                
        except KeyboardInterrupt:
            console.print("\n👋 Goodbye!", style="yellow")
        except Exception as e:
            console.print(f"❌ Error: {e}", style="red")
            raise
        finally:
            # Cleanup
            if client.temporal_client:
                await temporal_client.disconnect()
    
    # Show startup banner
    console.print(Panel.fit(
        "[bold blue]Obelisk Temporal Chat Client[/bold blue]\n"
        f"🌐 Temporal Server: {settings.temporal.server_url}\n"
        f"📝 Task Queue: {settings.temporal.task_queue}\n"
        f"🤖 Model: {settings.openrouter.model}",
        border_style="blue"
    ))
    
    # Run the async client
    asyncio.run(run_client())


if __name__ == "__main__":
    main() 