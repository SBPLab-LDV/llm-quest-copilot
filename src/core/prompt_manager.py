import os
import yaml
from typing import Dict, List, Optional

class PromptManager:
    def __init__(self, prompts_dir: str = "prompts"):
        """Initialize the PromptManager.
        
        Args:
            prompts_dir: Base directory containing all prompt files
        """
        self.prompts_dir = prompts_dir
        self.templates = {}
        self.context_examples = {}
        self.context_keywords = {}
        self._load_prompts()

    def _load_prompts(self):
        """Load all prompt templates, context examples, and keywords."""
        # Load templates
        template_dir = os.path.join(self.prompts_dir, "templates")
        for filename in os.listdir(template_dir):
            if filename.endswith(".yaml"):
                path = os.path.join(template_dir, filename)
                with open(path, 'r', encoding='utf-8') as f:
                    self.templates.update(yaml.safe_load(f))

        # Load context examples
        examples_dir = os.path.join(self.prompts_dir, "context_examples")
        for filename in os.listdir(examples_dir):
            if filename.endswith(".yaml"):
                path = os.path.join(examples_dir, filename)
                with open(path, 'r', encoding='utf-8') as f:
                    self.context_examples.update(yaml.safe_load(f))

        # Load context keywords
        keywords_path = os.path.join(self.prompts_dir, "context_keywords.yaml")
        with open(keywords_path, 'r', encoding='utf-8') as f:
            self.context_keywords = yaml.safe_load(f)

    def detect_context(self, user_input: str) -> str:
        """Detect the most likely context based on user input and keywords.
        
        Args:
            user_input: The user's input text
            
        Returns:
            The detected context (e.g., "醫師查房", "病房日常", etc.)
        """
        max_matches = 0
        detected_context = "一般對話"  # default context

        for context, keywords in self.context_keywords["dialogue_contexts"].items():
            matches = sum(1 for keyword in keywords if keyword in user_input)
            if matches > max_matches:
                max_matches = matches
                detected_context = context

        return detected_context

    def get_examples_for_context(self, context: str) -> List[Dict]:
        """Get relevant examples for a given context.
        
        Args:
            context: The dialogue context
            
        Returns:
            List of example dictionaries for the context
        """
        for context_data in self.context_examples.values():
            for entry in context_data:
                if entry["context"] == context:
                    return entry["examples"]
        return []

    def generate_prompt(self, 
                       user_input: str,
                       character_name: str,
                       persona: str,
                       backstory: str,
                       goal: str,
                       current_state: str,
                       conversation_history: Optional[List[str]] = None) -> str:
        """Generate a complete prompt by combining templates and context-specific examples.
        
        Args:
            user_input: The user's input text
            character_name: The character's name
            persona: The character's personality description
            backstory: The character's background story
            goal: The character's goal
            current_state: Current dialogue state
            conversation_history: Optional list of previous conversation turns
            
        Returns:
            Complete prompt string
        """
        # Detect context
        context = self.detect_context(user_input)
        
        # Get relevant examples
        examples = self.get_examples_for_context(context)
        
        # Format examples as text
        examples_text = ""
        for example in examples:
            examples_text += f"問題：{example['question']}\n"
            examples_text += f"關鍵字：{example['keyword']}\n"
            examples_text += "可能的回應：\n"
            for response in example['responses']:
                examples_text += f"- {response}\n"
            examples_text += "\n"

        # Get base template
        template = self.templates["character_response"]
        
        # Replace variables
        prompt = template.format(
            name=character_name,
            persona=persona,
            backstory=backstory,
            goal=goal,
            current_state=current_state,
            dialogue_context=context,
            dialogue_contexts=yaml.dump(self.context_keywords["dialogue_contexts"], 
                                      allow_unicode=True),
            context_examples=examples_text,
            conversation_history="\n".join(conversation_history) if conversation_history else "",
            user_input=user_input
        )
        
        return prompt

    def get_evaluation_prompt(self,
                            current_state: str,
                            player_input: str,
                            response: str) -> str:
        """Get the evaluation prompt with variables replaced.
        
        Args:
            current_state: Current dialogue state
            player_input: The user's input
            response: The character's response to evaluate
            
        Returns:
            Complete evaluation prompt string
        """
        template = self.templates["evaluation_prompt"]
        return template.format(
            current_state=current_state,
            player_input=player_input,
            response=response
        )
