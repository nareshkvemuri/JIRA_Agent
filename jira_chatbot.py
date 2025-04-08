import os
from datetime import datetime
from colorama import Fore, Style, init
import openai
import json
from typing import Any, Dict, List, Optional

# Initialize colorama for colored output
init()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")

def jira_jql_search(jql: str, fields: List[str]) -> Dict[str, Any]:
    """Wrapper for MCP JQL search function."""
    try:
        response = mcp_jira_mcp_jql_search(jql=jql, fields=fields)
        if isinstance(response, str):
            return json.loads(response)
        return response
    except Exception as e:
        print(f"{Fore.RED}Error in JQL search: {str(e)}{Style.RESET_ALL}")
        return {"issues": []}

def jira_get_issue(issue_key: str, fields: List[str]) -> Dict[str, Any]:
    """Wrapper for MCP get issue function."""
    try:
        response = mcp_jira_mcp_get_issue(issueIdOrKey=issue_key, fields=fields)
        if isinstance(response, str):
            return json.loads(response)
        return response
    except Exception as e:
        print(f"{Fore.RED}Error getting issue: {str(e)}{Style.RESET_ALL}")
        return None

class JiraChatbot:
    def __init__(self):
        self.conversation_history = []
        
    def _get_ai_response(self, prompt: str, system_prompt: str = "You are a helpful Jira assistant.") -> str:
        """Get AI response using OpenAI."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                *self.conversation_history[-5:],  # Keep last 5 messages for context
                {"role": "user", "content": prompt}
            ]
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=150
            )
            
            ai_response = response.choices[0].message.content
            self.conversation_history.append({"role": "user", "content": prompt})
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            return ai_response
        except Exception as e:
            return str(e)

    def _generate_jql_from_natural_language(self, query: str) -> str:
        """Convert natural language query to JQL using AI."""
        system_prompt = """
        You are a Jira query expert. Convert natural language queries to JQL (Jira Query Language).
        Only respond with the JQL query, nothing else.
        Examples:
        Input: "show me all high priority bugs assigned to me"
        Output: assignee = currentUser() AND priority = High AND type = Bug ORDER BY created DESC
        Input: "what are my open tasks"
        Output: assignee = currentUser() AND status = "Open" ORDER BY created DESC
        Input: "show my latest issues"
        Output: assignee = currentUser() ORDER BY created DESC
        Input: "find issues created today"
        Output: assignee = currentUser() AND created >= startOfDay() ORDER BY created DESC
        """
        
        try:
            response = self._get_ai_response(query, system_prompt)
            return response.strip()
        except Exception as e:
            print(f"{Fore.RED}Error generating JQL: {str(e)}{Style.RESET_ALL}")
            return "assignee = currentUser() ORDER BY created DESC"  # fallback query

    def _format_date(self, date_str: str) -> str:
        """Format date string to a more readable format."""
        try:
            dt = datetime.strptime(date_str[:19], '%Y-%m-%dT%H:%M:%S')
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return date_str

    def _format_issue_display(self, issue: Dict[str, Any], include_description: bool = True) -> str:
        """Format a single issue for display."""
        result = []
        result.append(f"\n{Fore.CYAN}Issue Key:{Style.RESET_ALL} {issue['key']}")
        result.append(f"{Fore.CYAN}Summary:{Style.RESET_ALL} {issue['fields']['summary']}")
        result.append(f"{Fore.CYAN}Status:{Style.RESET_ALL} {issue['fields']['status']['name']}")
        result.append(f"{Fore.CYAN}Priority:{Style.RESET_ALL} {issue['fields']['priority']['name']}")
        result.append(f"{Fore.CYAN}Created:{Style.RESET_ALL} {self._format_date(issue['fields']['created'])}")
        result.append(f"{Fore.CYAN}Updated:{Style.RESET_ALL} {self._format_date(issue['fields']['updated'])}")
        
        if include_description and issue['fields'].get('description'):
            result.append(f"{Fore.CYAN}Description:{Style.RESET_ALL} {issue['fields']['description']}")
        
        return "\n".join(result)

    def get_my_issues(self, natural_query: Optional[str] = None) -> str:
        """Fetch issues assigned to the current user."""
        try:
            # Generate JQL from natural language if provided
            if natural_query:
                jql = self._generate_jql_from_natural_language(natural_query)
                print(f"{Fore.YELLOW}Generated JQL:{Style.RESET_ALL} {jql}")
            else:
                jql = "assignee = currentUser() ORDER BY created DESC"

            # Make the tool call
            response = jira_jql_search(
                jql=jql,
                fields=["summary", "status", "priority", "created", "updated", "description"]
            )
            
            if not response or not response.get("issues"):
                return f"{Fore.YELLOW}No issues found matching your query.{Style.RESET_ALL}"
            
            issues = response.get("issues", [])
            total = response.get("total", len(issues))
            
            result = [f"{Fore.GREEN}Found {total} issue(s):{Style.RESET_ALL}"]
            
            for issue in issues:
                result.append(self._format_issue_display(issue, include_description=False))
                result.append("-" * 50)
            
            return "\n".join(result)
            
        except Exception as e:
            return f"{Fore.RED}Error fetching issues: {str(e)}{Style.RESET_ALL}"

    def get_issue_details(self, issue_key: str) -> str:
        """Get detailed information about a specific issue."""
        try:
            # Make the tool call
            response = jira_get_issue(
                issue_key=issue_key,
                fields=["summary", "status", "priority", "description", "created", "updated"]
            )
            
            if not response:
                return f"{Fore.RED}Issue {issue_key} not found.{Style.RESET_ALL}"
            
            result = [f"{Fore.GREEN}Details for issue {issue_key}:{Style.RESET_ALL}"]
            result.append(self._format_issue_display(response, include_description=True))
            return "\n".join(result)
            
        except Exception as e:
            return f"{Fore.RED}Error fetching issue details: {str(e)}{Style.RESET_ALL}"

    def process_command(self, command: str) -> str:
        """Process user commands."""
        command = command.lower().strip()
        
        if command in ['my issues', 'show my issues', 'list issues']:
            return self.get_my_issues()
        elif command.startswith('details '):
            issue_key = command.split('details ')[1].strip().upper()
            return self.get_issue_details(issue_key)
        elif command in ['help', '?']:
            return self._get_help()
        elif command in ['exit', 'quit', 'bye']:
            return 'exit'
        else:
            # Try to interpret the command as a natural language query
            return self.get_my_issues(command)

    def _get_help(self) -> str:
        """Return help information."""
        help_text = [
            f"\n{Fore.GREEN}Available commands:{Style.RESET_ALL}",
            "1. Basic commands:",
            "   - my issues: Show all issues assigned to you",
            "   - details [ISSUE-KEY]: Show detailed information about a specific issue",
            "   - help: Show this help message",
            "   - exit: Exit the chatbot",
            "",
            "2. Natural language queries (examples):",
            "   - show me my high priority tasks",
            "   - what issues are in To Do status",
            "   - show my latest created issues",
            "   - find issues created today",
            "",
            f"{Fore.YELLOW}Tip: You can ask about your issues in plain English!{Style.RESET_ALL}"
        ]
        return "\n".join(help_text)

def main():
    print(f"{Fore.CYAN}Initializing Jira Chatbot with AI capabilities...{Style.RESET_ALL}")
    chatbot = JiraChatbot()
    
    print(f"\n{Fore.GREEN}Welcome to AI-powered Jira Chatbot!{Style.RESET_ALL}")
    print("Type 'help' for available commands or 'exit' to quit.")
    print(f"{Fore.YELLOW}You can use natural language to query your issues!{Style.RESET_ALL}")
    
    while True:
        try:
            user_input = input(f"\n{Fore.YELLOW}You:{Style.RESET_ALL} ").strip()
            
            if not user_input:
                continue
                
            response = chatbot.process_command(user_input)
            
            if response == 'exit':
                print(f"\n{Fore.GREEN}Goodbye!{Style.RESET_ALL}")
                break
                
            print(f"\n{Fore.MAGENTA}Bot:{Style.RESET_ALL} {response}")
            
        except KeyboardInterrupt:
            print(f"\n{Fore.GREEN}Goodbye!{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"\n{Fore.RED}An error occurred: {str(e)}{Style.RESET_ALL}")

if __name__ == "__main__":
    main() 