
tasks = []


def add_task(title, due_date):
    task = {
        "id": len(tasks) + 1,
        "title": title,
        "due_date": due_date
    }

    tasks.append(task)

    return {
        "status": "success",
        "message": f"Task '{title}' added successfully"
    }


def list_tasks():
    return {
        "tasks": tasks
    }
