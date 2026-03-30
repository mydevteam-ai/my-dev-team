from langchain_core.messages import HumanMessage
from .base_extension import CrewExtension

class HumanInTheLoop(CrewExtension):
    """Extension that pauses the workflow to get human input at the 'human' node."""

    def on_pause(self, thread_id: str, current_state: dict, next_node: str) -> dict | None:
        if next_node != 'human':
            return None
        if current_state.get('clarification_question'):
            return self._handle_clarification(current_state)
        if current_state.get('specs'):
            return self._handle_plan_approval(current_state)
        return None

    def _handle_clarification(self, current_state: dict) -> dict:
        question = current_state.get('clarification_question', 'The team needs your input.')
        print("\n" + "="*50)
        print("🛑 THE CREW NEEDS YOUR INPUT")
        print("="*50)
        print(f"Question: {question}\n")
        user_input = input("Your Answer (or type 'exit' to abort): ")
        if user_input.lower() in ['exit', 'quit']:
            print("Aborting project...")
            return {
                'abort_requested': True,
                'communication_log': self.communication("Aborted the workflow.")
            }
        return {
            'messages': [HumanMessage(content=user_input)],
            'communication_log': self.communication(user_input)
        }

    def _handle_plan_approval(self, current_state: dict) -> dict:
        pending_tasks = current_state.get('pending_tasks', [])
        if not pending_tasks:
            return self._handle_spec_approval(current_state)
        return self._handle_task_plan_approval(current_state)

    def _handle_spec_approval(self, current_state: dict) -> dict:
        specs = current_state.get('specs', 'No specifications available.')
        print("\n" + "="*60)
        print("📄 SPECIFICATION APPROVAL REQUIRED")
        print("="*60)
        print(specs)
        print("\n" + "="*60)
        print("Type 'approved' to proceed to architecture, or type feedback to request rework.")
        print("Type 'exit' to abort.")
        print("="*60)
        user_input = input("\nYour decision: ").strip()
        if user_input.lower() in ['exit', 'quit']:
            print("Aborting project...")
            return {
                'abort_requested': True,
                'communication_log': self.communication("Aborted during spec approval.")
            }
        if user_input.lower() == 'approved':
            print("✅ Specifications approved! Proceeding to architecture...")
            return {
                'specs_approved': True,
                'communication_log': self.communication("Specifications approved by user.")
            }
        print("🔄 Sending specifications back for rework...")
        return {
            'specs': '',
            'specs_approved': False,
            'messages': [HumanMessage(content=f"Specification feedback from user: {user_input}")],
            'communication_log': self.communication(f"Specification rework requested: {user_input}")
        }

    def _handle_task_plan_approval(self, current_state: dict) -> dict:
        specs = current_state.get('specs', 'No specifications available.')
        pending_tasks = current_state.get('pending_tasks', [])
        print("\n" + "="*60)
        print("📋 TASK PLAN APPROVAL REQUIRED")
        print("="*60)
        print("\n📄 SPECIFICATIONS:\n")
        print(specs)
        print("\n📝 TASK PLAN:\n")
        for i, task in enumerate(pending_tasks, 1):
            deps = ', '.join(task.get('dependencies', [])) or 'none'
            print(f"  {i}. {task['task_name']}")
            print(f"     Story: {task['user_story']}")
            print(f"     Dependencies: {deps}")
        print("\n" + "="*60)
        print("Type 'approved' to start development, or type feedback to request rework.")
        print("Type 'exit' to abort.")
        print("="*60)
        user_input = input("\nYour decision: ").strip()
        if user_input.lower() in ['exit', 'quit']:
            print("Aborting project...")
            return {
                'abort_requested': True,
                'communication_log': self.communication("Aborted during task plan approval.")
            }
        if user_input.lower() == 'approved':
            print("✅ Task plan approved! Starting development...")
            return {
                'current_phase': 'development',
                'tasks_approved': True,
                'communication_log': self.communication("Task plan approved by user.")
            }
        print("🔄 Sending task plan back for rework...")
        return {
            'pending_tasks': [],
            'messages': [HumanMessage(content=f"Task plan feedback from user: {user_input}")],
            'communication_log': self.communication(f"Task plan rework requested: {user_input}")
        }
