class MockProvider:
 async def models(self):return [{'id':'mock','object':'model'}]
 async def chat(self,p):return {'id':'chatcmpl-mock','object':'chat.completion','created':0,'model':'mock','choices':[{'index':0,'message':{'role':'assistant','content':'Mock response: '+p['messages'][-1]['content']},'finish_reason':'stop'}],'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
