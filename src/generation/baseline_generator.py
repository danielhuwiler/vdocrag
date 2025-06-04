from generation.base_generator import BaseGenerator, Response

class BaselineGenerator(BaseGenerator):
    def generate(self, retrieved_data, query):        
        user_prompt = f"Question: {query}\n\nRetrieved Data:\n{retrieved_data}"
        llm_response = self.llm_client.generate(system_prompt=self.system_prompt, user_prompt=user_prompt)
        return Response(answer=llm_response)