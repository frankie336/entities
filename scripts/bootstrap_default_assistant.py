# scripts/bootstrap_default_assistant.py
import argparse
import os
import sys

try:
    from entities_api.constants.assistant import BASE_TOOLS, DEFAULT_MODEL
    from entities_api.services.logging_service import LoggingUtility
    from entities_api.system_message.assembly import assemble_instructions
    from projectdavid import Entity
    from projectdavid_common import ValidationInterface
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please ensure:")
    print(
        "  1. Packages 'projectdavid', 'projectdavid_common', and 'entities_api' are installed within the 'api' container image."
    )
    print(
        "  2. The script is executed from a path where Python can find these packages (e.g., '/app/entities_api/services' if '/app' is the project root inside container)."
    )
    sys.exit(1)


# --- Initialize necessary components ---
validate = ValidationInterface()
logging_utility = LoggingUtility()


class AssistantSetupService:
    def __init__(self, client: Entity):
        """Initializes the service with a pre-configured API client."""
        if not isinstance(client, Entity):
            raise TypeError(
                "AssistantSetupService requires an initialized projectdavid.Entity client."
            )
        self.client = client
        self.logging_utility = logging_utility

    def create_and_associate_tools(self, function_definitions, assistant_id):
        """Creates tools if needed and associates them with the assistant."""
        self.logging_utility.info(f"Checking/Creating tools for assistant: {assistant_id}")
        created_tool_ids = []
        associated_tool_ids = []

        for func_def in function_definitions:
            tool_name = func_def.get("function", {}).get("name")
            if not tool_name:
                self.logging_utility.warning("Skipping tool definition with missing name.")
                continue

            tool_id_to_associate = None
            # --- Find existing tool (Optional - depends on SDK/API behavior) ---
            # try:
            #     # This assumes a reliable way to find tools by name. Be cautious.
            #     existing_tool = self.client.tools.get_tool_by_name(tool_name)
            #     if existing_tool:
            #         self.logging_utility.info(f"Tool '{tool_name}' found (ID: {existing_tool.id}).")
            #         tool_id_to_associate = existing_tool.id
            # except Exception as retrieval_error: # Replace with specific NotFoundError if possible
            #     self.logging_utility.debug(f"Tool '{tool_name}' not found, will create. Hint: {retrieval_error}")
            # --- End Find existing tool ---

            # --- Create Tool if not found (or if find logic is omitted) ---
            if not tool_id_to_associate:  # This condition is always met if find logic is omitted
                try:
                    tool_function = validate.ToolFunction(function=func_def["function"])
                    new_tool = self.client.tools.create_tool(
                        name=tool_name,
                        type="function",
                        function=tool_function.model_dump(),
                    )
                    tool_id_to_associate = new_tool.id
                    created_tool_ids.append(new_tool.id)
                    self.logging_utility.info(f"Created tool: '{tool_name}' (ID: {new_tool.id})")
                except Exception as e:
                    # Handle potential "tool already exists" errors if name must be unique
                    self.logging_utility.error(
                        f"Tool creation failed for '{tool_name}': {e}", exc_info=True
                    )
                    # Attempt to find the tool by name again if creation failed due to existence? Risky.
                    # For now, we just skip association if creation fails.
                    continue

            # --- Associate Tool ---
            if tool_id_to_associate:
                try:
                    self.client.tools.associate_tool_with_assistant(
                        tool_id=tool_id_to_associate, assistant_id=assistant_id
                    )
                    associated_tool_ids.append(tool_id_to_associate)
                    self.logging_utility.info(
                        f"Ensured tool '{tool_name}' (ID: {tool_id_to_associate}) is associated with assistant {assistant_id}"
                    )
                except Exception as e:
                    # Handle potential "already associated" errors if API doesn't ignore them
                    self.logging_utility.error(
                        f"Failed to associate tool ID {tool_id_to_associate} with assistant {assistant_id}: {e}",
                        exc_info=True,
                    )

        self.logging_utility.info(
            f"Tool setup summary for Assistant {assistant_id}: {len(created_tool_ids)} created, {len(associated_tool_ids)} associated/verified."
        )

    def setup_assistant_with_tools(
        self,
        user_id: str,  # Added user_id here for clarity, though not directly used in sample API calls
        assistant_name: str,
        assistant_description: str,
        model: str,
        instructions: str,
        function_definitions: list,
    ):
        """Gets or creates the 'default' assistant and associates tools."""
        target_assistant_id = "default"  # Logical ID used for get-or-create

        try:
            assistant = self.client.assistants.retrieve_assistant(target_assistant_id)
            self.logging_utility.info(
                f"Found existing assistant '{assistant.name}' with logical ID '{target_assistant_id}' (Actual ID: {assistant.id})"
            )
            # Potential Update Logic (Uncomment and adapt if needed)
            # update_payload = {
            #     "name": assistant_name, "description": assistant_description,
            #     "model": model, "instructions": instructions
            # }
            # updated_assistant = self.client.assistants.update_assistant(assistant.id, **update_payload)
            # self.logging_utility.info(f"Updated existing assistant {assistant.id}.")
            # assistant = updated_assistant # Use the updated object

        except Exception as e:  # Replace with specific NotFoundError if possible
            self.logging_utility.warning(
                f"Assistant with logical ID '{target_assistant_id}' not found (Hint: {e}). Creating new one."
            )
            try:
                assistant = self.client.assistants.create_assistant(
                    name=assistant_name,
                    description=assistant_description,
                    model=model,
                    instructions=instructions,
                    assistant_id=target_assistant_id,  # Attempt to assign logical ID (API support dependent)
                    # user_id=user_id # Check if API requires user_id for creation
                )
                self.logging_utility.info(
                    f"Created new assistant: '{assistant.name}' (Logical ID: '{target_assistant_id}', Actual ID: {assistant.id})"
                )
            except Exception as create_e:
                self.logging_utility.error(
                    f"Failed to create assistant '{assistant_name}': {create_e}", exc_info=True
                )
                raise  # Critical failure

        if not assistant or not hasattr(assistant, "id"):
            self.logging_utility.error("Failed to obtain a valid assistant object.")
            raise ValueError("Could not retrieve or create the target assistant.")

        # Associate tools
        self.create_and_associate_tools(function_definitions, assistant.id)
        return assistant

    def orchestrate_default_assistant(self, user_id: str):
        """Main orchestration flow for the 'default' assistant for a given user context."""
        self.logging_utility.info(
            f"Starting default assistant orchestration for user context: {user_id}"
        )
        try:
            instructions = assemble_instructions()
            assistant = self.setup_assistant_with_tools(
                user_id=user_id,  # Pass context
                assistant_name="Q",
                assistant_description="Default general-purpose assistant",
                model=DEFAULT_MODEL,
                instructions=instructions,
                function_definitions=BASE_TOOLS,
            )
            self.logging_utility.info(
                f"Orchestration completed for user {user_id}. Assistant ready (ID: {assistant.id})."
            )
            return assistant
        except Exception as e:
            self.logging_utility.critical(
                f"Critical failure in orchestration for user {user_id}: {e}", exc_info=True
            )
            raise


# --- Main Execution Block (Modified for Container Execution) ---
if __name__ == "__main__":
    # --- Define default base URL for inside container ---
    # Processes inside the 'api' container can typically reach the API on localhost
    DEFAULT_INTERNAL_BASE_URL = "http://localhost:9000"

    parser = argparse.ArgumentParser(
        description="Set up or verify the 'default' assistant and its tools (run inside API container).",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--api-key",
        help="REQUIRED: The API key for authenticating (e.g., the user's key or an admin key).",
    )
    parser.add_argument(
        "--user-id",
        help="REQUIRED: The User ID context for this operation (e.g., whose assistant setup this is for).",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv(
            "ASSISTANTS_BASE_URL", DEFAULT_INTERNAL_BASE_URL
        ),  # Prioritize env, then internal default
        help=f"Optional base URL for the API endpoint. Defaults to ASSISTANTS_BASE_URL env var or {DEFAULT_INTERNAL_BASE_URL}.",
    )

    args = parser.parse_args()

    # --- Get Required Values ---
    api_key = args.api_key
    user_id = args.user_id
    base_url = args.base_url

    # --- Check for missing required arguments (more robust than prompting in exec) ---
    if not api_key:
        parser.error("Missing required argument: --api-key. Please provide the API key.")
    if not user_id:
        parser.error("Missing required argument: --user-id. Please provide the User ID.")

    # --- Print Configuration Being Used ---
    print("\n--- Assistant Setup Configuration (inside container) ---")
    print(f"User ID Context: {user_id}")
    print(f"API Key: {'*' * (len(api_key) - 4)}{api_key[-4:]}")  # Mask key
    print(f"Base URL: {base_url}")
    print("-" * 50)

    # --- Initialize Client ---
    try:
        print(f"Initializing API client with Base URL: {base_url}...")
        api_client = Entity(api_key=api_key, base_url=base_url)

        # Optional: Validate credentials early
        try:
            print("Validating credentials by retrieving user...")
            retrieved_user = api_client.users.retrieve_user(user_id)
            print(
                f"Credentials valid (User '{getattr(retrieved_user, 'email', user_id)}' retrieved)."
            )
        except Exception as check_err:
            print(
                f"\nWarning: Could not validate credentials/user_id ({user_id}). Error: {check_err}",
                file=sys.stderr,
            )
            print("Continuing execution, but API calls might fail.", file=sys.stderr)

        print("API Client initialized.")

    except Exception as e:
        print(f"\nError: Failed to initialize API client: {e}", file=sys.stderr)
        logging_utility.error("Failed to initialize API client", exc_info=True)
        sys.exit(1)

    # --- Instantiate and Run Service ---
    try:
        service = AssistantSetupService(client=api_client)
        print("\nStarting assistant orchestration...")
        logging_utility.info(
            f"Initiating orchestration via script execution (User: {user_id}, BaseURL: {base_url})"
        )
        assistant = service.orchestrate_default_assistant(user_id=user_id)

        if assistant:
            print("\n--- Orchestration Successful ---")
            print(f"Assistant Name: {getattr(assistant, 'name', 'N/A')}")
            print(f"Assistant ID:   {getattr(assistant, 'id', 'N/A')}")
            print("Tools should now be created/associated.")
        else:
            # This path unlikely if orchestrate_default_assistant raises on failure
            print("\n--- Orchestration Finished (No Assistant Object Returned) ---")
            print("Check logs for details.")

    except Exception as e:
        print("\n--- Orchestration Failed ---", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nScript finished.")
