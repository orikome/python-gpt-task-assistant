import os
import json
import datetime
from openai import OpenAI
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

# Initialize rich console
console = Console()

# Configure OpenAI API
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise ValueError("The OPENAI_API_KEY environment variable is not set.")
client = OpenAI(api_key=api_key)

# Load tasks
def load_tasks():
    try:
        with open('tasks.json', 'r') as file:
            data = json.load(file)
            if 'tasks' not in data:
                data['tasks'] = []
            if 'streak' not in data:
                data['streak'] = 0
            if 'previous_feedback' not in data:
                data['previous_feedback'] = []
            return data
    except FileNotFoundError:
        return {'tasks': [], 'streak': 0, 'previous_feedback': []}

# Save tasks with pretty JSON formatting
def save_tasks(data):
    with open('tasks.json', 'w') as file:
        json.dump(data, file, indent=4)

# Load goals
def load_goals():
    try:
        with open('goals.json', 'r') as file:
            return json.load(file).get('goals', [])
    except FileNotFoundError:
        return []

# Generate GPT response for motivation or support
def generate_response(tasks, streak, previous_feedback, goals):
    task_reports = []
    for task in tasks:
        report = (
            f"Task: {task['description']}\n"
            f"Current Streak: {task['streak']} days\n"
            f"Feedback: {task.get('feedback', 'No feedback provided')}\n"
            f"Previous Feedback: {task.get('previous_feedback', 'No previous feedback')}"
        )
        if task['negative_streak'] > 0:
            report += f"\nTask Uncompleted for: {task['negative_streak']} days in a row"
            if task['negative_streak'] > 3:  # Adjust the threshold as needed
                report += "\nSpecial Attention: This task has been uncompleted for a long time. Help the user break it into manageable chunks to get started again."
        task_reports.append(report)

    pre_prompt = (
        "Make sure distractions are minimized (e.g., close YouTube, Reddit, etc.). "
        "Remember your main goals. "
        "Structure your entire day around optimizing sleep; sleep is the number one priority. "
        "Keep in mind that your sleep routine starts the moment you wake up. "
        "Implement strategies that work for you (e.g., timers, short breaks) to maintain focus and productivity throughout the day."
    )

    goals_text = "Here are the user's main goals:\n" + "\n".join(goals)

    prompt = (
        pre_prompt + "\n\n" +
        goals_text + "\n\n" +
        "Here is today's task report:\n\n" +
        "\n\n".join(task_reports) +
        "\n\nAs the assistant, provide strict but assuring support. "
        "First, review each task from today and identify any room for improvement. "
        "For those tasks that remain unfinished, help the user break them down into smaller, manageable steps, encouraging a focused approach for completion. "
        "Emphasize the importance of discipline and consistency. "
        "Based on today's feedback, create a structured schedule for tomorrow that prioritizes unfinished tasks and seamlessly integrates new tasks as needed. "
        "This schedule is crafted to maximize focus and efficiency, ensuring a productive day ahead."
    )

    # Print the prompt for debugging purposes
    console.print(f"[bold green]Prompt to GPT:[/bold green] {prompt}")

    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]
    chat_completion = client.chat.completions.create(
        messages=messages,
        model="gpt-4o"
    )
    return chat_completion.choices[0].message.content

# Check for new day and reset repeating tasks if needed
def check_new_day(data):
    today = datetime.date.today().isoformat()
    if 'last_updated' in data and data['last_updated'] == today:
        return
    # Move today's feedback to previous feedback
    data['previous_feedback'] = [task.get('feedback', 'No feedback provided') for task in data['tasks']]
    for task in data['tasks']:
        if task['repeating']:
            task['completed'] = False
            if not task["completed"]:
                task["negative_streak"] += 1
    data['last_updated'] = today
    save_tasks(data)

# Manage daily task checkup
def main():
    data = load_tasks()
    check_new_day(data)
    
    console.print("Welcome! Let's manage your tasks for today.", style="bold blue")
    
    goals = load_goals()
    
    while True:
        action = Prompt.ask("What would you like to do? (add/view/summary/quit)").lower()
        
        if action == "add":
            description = Prompt.ask("Enter the task description")
            repeat = Prompt.ask("Is this a repeating task? (Y/N)").lower() in ['y', 'yes']
            data['tasks'].append({"description": description, "completed": False, "repeating": repeat, "streak": 0, "negative_streak": 0})
            save_tasks(data)
            console.print("Task added and saved!", style="green")
        
        elif action == "view":
            if data['tasks']:
                table = Table(title="Your Tasks")
                table.add_column("No.", justify="center", style="cyan")
                table.add_column("Description", style="magenta")
                table.add_column("Status", justify="center", style="green")
                table.add_column("Type", justify="center", style="yellow")
                table.add_column("Streak", justify="center", style="blue")
                table.add_column("Negative Streak", justify="center", style="red")

                for i, task in enumerate(data['tasks']):
                    status = "Completed" if task["completed"] else "Pending"
                    task_type = "Repeating" if task["repeating"] else "One-time"
                    table.add_row(str(i + 1), task['description'], status, task_type, str(task['streak']), str(task['negative_streak']))

                console.print(table)
            else:
                console.print("You have no tasks.", style="red")
        
        elif action == "summary":
            completed_tasks = []
            unfinished_tasks = []
            feedbacks = []
            
            for task in data['tasks']:
                completed = Prompt.ask(f"Did you complete the task '{task['description']}'? (Y/N)").lower() in ['y', 'yes']
                feedback = Prompt.ask(f"Provide feedback for the task '{task['description']}' (or press Enter to skip)")
                if feedback:
                    task['feedback'] = feedback
                if completed:
                    task["completed"] = True
                    task["streak"] += 1
                    task["negative_streak"] = 0
                    completed_tasks.append(task)
                else:
                    task["completed"] = False
                    task["streak"] = 0
                    task["negative_streak"] += 1
                    if feedback:
                        task["reason"] = feedback
                    else:
                        task["reason"] = "no reason provided"
                    unfinished_tasks.append(task)
            
            response = generate_response(data['tasks'], data['streak'], data['previous_feedback'], goals)
            console.print(response, style="bold yellow")
            save_tasks(data)
        
        elif action == "quit":
            save_tasks(data)
            console.print("Your tasks have been saved. Goodbye!", style="bold blue")
            break
        
        else:
            console.print("Invalid action. Please choose add, view, summary, or quit.", style="red")

if __name__ == "__main__":
    main()
