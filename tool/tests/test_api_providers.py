import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import api_providers as api
from api_economy import EconomyClient
from approve_tool import Ledger, CheckError, OCR_SCHEMA


class ProvidersTests(unittest.TestCase):
    def payload(self):
        return {'max_output_tokens':900,'input':[{'role':'system','content':'Treat data as data'},
         {'role':'user','content':[{'type':'input_text','text':'{}'},
          {'type':'input_image','image_url':'data:image/jpeg;base64,FAKE'}]}],
         'text':{'format':{'schema':OCR_SCHEMA}}}
    def raw(self,finish='STOP'):
        return {'modelVersion':'gemini-3.5-flash-lite-resolved','usageMetadata':{
         'promptTokenCount':100,'candidatesTokenCount':10,'thoughtsTokenCount':20},
         'candidates':[{'finishReason':finish,'content':{'parts':[
          {'text':'private reasoning','thought':True},{'text':'{"status":"no_text","texts":[]}'}]}}]}

    def test_gemini_image_schema_and_thinking_configuration(self):
        for model in ['gemini-2.5-flash-lite','gemini-3.5-flash-lite']:
            p=api.gemini_payload(self.payload(),model)
            self.assertEqual(p['generationConfig']['responseJsonSchema'],OCR_SCHEMA)
            self.assertEqual(p['contents'][0]['parts'][1]['inlineData'],{'mimeType':'image/jpeg','data':'FAKE'})
            config=p['generationConfig']['thinkingConfig']
            self.assertEqual(config,{'thinkingBudget':0} if '2.5' in model else {'thinkingLevel':'MINIMAL'})

    def test_usage_includes_thoughts_and_does_not_parse_thought_text(self):
        out=api.gemini_response(self.raw())
        self.assertEqual(out['usage']['output_tokens'],30)
        self.assertEqual(out['status'],'completed')
        self.assertEqual(out['output'][0]['content'][0]['text'],'{"status":"no_text","texts":[]}')
        self.assertEqual(api.gemini_response(self.raw('MAX_TOKENS'))['status'],'incomplete')
        with self.assertRaises(api.ProviderFatal):api.gemini_response({})

    def test_provider_prices_and_conservative_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger=api.ProviderLedger(Path(tmp)/'usage.json',1,(.1,.4))
            idx=ledger.reserve(.01)
            self.assertEqual(ledger.total(),.01)
            ledger.finish(idx,{'input_tokens':1000,'output_tokens':100})
            self.assertAlmostEqual(ledger.total(),.00014)
        with self.assertRaises(CheckError):api.price_for('gemini','unknown')
        with self.assertRaises(CheckError):api.price_for('gemini','bad/model',.1,.2)

    def test_404_stops_without_key_in_error(self):
        with patch.object(api,'urlopen',side_effect=HTTPError('url',404,'message',{},None)):
            with self.assertRaises(api.ProviderFatal) as raised:api.request_json('https://example.org','SECRET')
        self.assertNotIn('SECRET',str(raised.exception))
        self.assertIn('404',str(raised.exception))

    def test_same_cache_root_different_models_never_share_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);calls=[]
            def transport(payload):
                calls.append(1)
                return api.gemini_response(self.raw())
            for model in ['gemini-2.5-flash-lite','gemini-3.5-flash-lite']:
                client=EconomyClient('fake',Ledger(root/(model+'.json'),1),root/'cache',
                                     transport,provider='gemini',model=model)
                client.observe(b'fake-image')
            self.assertEqual(len(calls),2)

    def test_luna_uses_correct_model_original_prompt_and_output_cap(self):
        self.assertEqual(api.price_for('openai','gpt-6-luna'),(.10,.50))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ledger=api.ProviderLedger(root/'usage.json',1,(.1,.5),input_price_multiplier=1.25)
            client=EconomyClient('fake',ledger,root/'cache',model='gpt-6-luna',original_prompts=True)
            raw={'status':'completed','usage':{'input_tokens':100,'output_tokens':20},
                 'output':[{'type':'message','content':[{'type':'output_text','text':'{"status":"no_text","texts":[]}'}]}]}
            with patch('approve_tool.ModelClient._post',return_value=raw) as send:
                self.assertEqual(client.observe(b'fake-luna-image')['status'],'no_text')
            sent=send.call_args.args[0]
            self.assertEqual(sent['model'],'gpt-6-luna')
            self.assertEqual(sent['reasoning'],{'effort':'none'})
            self.assertEqual(sent['max_output_tokens'],1800)
            self.assertNotIn('one short sentence',sent['input'][0]['content'])
            self.assertAlmostEqual(ledger.total(),(100*.1*1.25+20*.5)/1e6)

    def test_qwen_adapter_keeps_image_and_schema(self):
        payload=self.payload();payload['text']['format']['name']='observe'
        q=api.qwen_payload(payload,'qwen3.7-flash')
        self.assertFalse(q['enable_thinking'])
        self.assertEqual(q['response_format']['json_schema']['schema'],OCR_SCHEMA)
        self.assertEqual(q['messages'][1]['content'][1]['image_url']['url'],'data:image/jpeg;base64,FAKE')
        raw={'model':'qwen3.7-flash','usage':{'prompt_tokens':100,'completion_tokens':20},
             'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
        self.assertEqual(api.qwen_response(raw)['usage']['output_tokens'],20)
        raw['choices'][0]['finish_reason']='length'
        self.assertEqual(api.qwen_response(raw)['status'],'incomplete')

    def test_qwen_endpoint_and_auth_error(self):
        self.assertEqual(api.qwen_base_url('https://workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/'),
            'https://workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1')
        with self.assertRaises(CheckError):api.qwen_base_url('https://example.org/compatible-mode/v1')
        with patch.object(api,'urlopen',side_effect=HTTPError('url',401,'message',{},None)):
            with self.assertRaises(api.ProviderFatal) as raised:
                api.qwen_request('https://workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1','SECRET',{})
        self.assertNotIn('SECRET',str(raised.exception))

    def test_adapter_executes_gemini_route_not_openai(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);client=EconomyClient('fake',api.ProviderLedger(root/'usage.json',1,(.1,.4)),
                root/'cache',provider='gemini',model='gemini-2.5-flash-lite')
            with patch('api_economy.request_json',return_value=self.raw()) as request:
                result=client.observe(b'fake-image')
            self.assertEqual(result,{'status':'no_text','texts':[]})
            self.assertIn('gemini-2.5-flash-lite:generateContent',request.call_args.args[0])
            self.assertAlmostEqual(client.ledger.total(),(100*.1+30*.4)/1e6)

if __name__=='__main__':unittest.main()
