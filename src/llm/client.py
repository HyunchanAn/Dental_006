import openai


class LLMClient:
    """
    A client to interact with the local llamafile server, which is compatible
    with the OpenAI API.
    """

    def __init__(self, base_url="http://127.0.0.1:11434/v1"):
        """
        Initializes the OpenAI client to connect to the local server.
        Args:
            base_url (str): The base URL of the local llamafile server.
        """
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key="sk-no-key-required",  # API key is not needed for local server
        )

    def get_completion(self, messages, model="gemma2", temperature=0.7):
        """
        Gets a completion from the local LLM.

        Args:
            messages (list): A list of message dictionaries (e.g., [{"role": "user", "content": "Hello"}]).
            model (str): The model name to use. This is required by the API but the
                         actual model is the one running in the llamafile server.
            temperature (float): The sampling temperature.

        Returns:
            str: The content of the assistant's reply.
        """
        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            return completion.choices[0].message.content
        except openai.APIConnectionError:
            print(f"Error connecting to the Ollama server at {self.client.base_url}.")
            print("Please ensure the Ollama application is running.")
            return None


if __name__ == "__main__":
    # This is an example of how to use the LLMClient.
    # Make sure your llamafile server is running before executing this.

    # Check if the server is expected to be running
    print("Attempting to connect to local LLM server...")

    llm_client = LLMClient()

    # Example prompt
    system_prompt = "You are a helpful assistant specializing in systematic reviews."
    user_prompt = "What are the key components of a PICO framework?"

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    response = llm_client.get_completion(messages)

    if response:
        print("\n--- LLM Response ---")
        print(response)
        print("--------------------")
