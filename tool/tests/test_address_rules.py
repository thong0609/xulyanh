import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from address_rules import split_address,rank_addresses
from grouped_pipeline import GroupPipeline
from test_grouped_pipeline import Model,Fetch,row,items

class AddressTests(unittest.TestCase):
    def candidates(self):
        return [{'record_id':rid,'address':split_address(name,'juno')} for rid,name in [
          ('R0','Juno - 319 Ấp Bắc, P.5, Tp.Mỹ Tho, Tiền Giang'),
          ('R1','Juno - 102 Nguyễn Trãi, Phường 3, Quận 5, Hồ Chí Minh')]]
    def rank(self,text):
        return rank_addresses(self.candidates(),[{'text':text,'evidence_ids':['caption'],'scope':'figure'}],{'R0','R1'})
    def test_extract_house_street_branch_and_city(self):
        a=self.candidates()[0]['address']
        self.assertEqual(a['house_number'],'319');self.assertEqual(a['street'],'ap bac')
        self.assertEqual(a['ward'],'5');self.assertEqual(a['city'],'tien giang')
        self.assertEqual(split_address('Juno Vincom Plaza Bắc Giang (TP. Bắc Giang)','juno')['branch'],
                         'vincom plaza bac giang')
    def test_unique_address_in_image_context_wins(self):
        winner,_=self.rank('JUNO 102 Nguyễn Trãi, P.3, Q.5, Hồ Chí Minh')
        self.assertEqual(winner['record_id'],'R1')
    def test_city_only_or_wrong_house_number_does_not_identify_branch(self):
        for text in ['Juno tại Hồ Chí Minh','Juno 103 Nguyễn Trãi, Q.5, Hồ Chí Minh']:
            self.assertIsNone(self.rank(text)[0])
    def test_directory_containing_both_addresses_does_not_pick_longest(self):
        self.assertIsNone(self.rank('319 Ấp Bắc, Mỹ Tho, Tiền Giang; 102 Nguyễn Trãi, Q.5, Hồ Chí Minh')[0])
    def test_conflicting_image_occurrences_are_ambiguous(self):
        contexts=[{'text':t,'evidence_ids':[str(i)]} for i,t in enumerate(
                  ['319 Ấp Bắc, Tiền Giang','102 Nguyễn Trãi, Hồ Chí Minh'])]
        self.assertIsNone(rank_addresses(self.candidates(),contexts,{'R0','R1'})[0])
    def test_group_prefers_second_branch_over_first_brand_url_hit(self):
        m=Model();f=Fetch('Juno 102 Nguyễn Trãi, Phường 3, Quận 5, Hồ Chí Minh')
        r=GroupPipeline(m,f).process_group(items(
          row('Juno - 319 Ấp Bắc, P.5, Tp.Mỹ Tho, Tiền Giang',url='https://juno.vn/image.jpg'),
          row('Juno - 102 Nguyễn Trãi, Phường 3, Quận 5, Hồ Chí Minh',url='https://juno.vn/image.jpg')))
        self.assertEqual([x['approve'] for x in r],['no','yes'])
        self.assertEqual(r[1]['reason'],'GROUP_ADDRESS_MATCH')
        self.assertTrue(r[1]['checks']['group_decision']['proof']['branch_identified'])
        self.assertEqual(m.calls,0)
    def test_global_directory_text_does_not_identify_image_branch(self):
        class Directory(Fetch):
            def page(self,*a):
                p=super().page(*a);p['text']='Juno 102 Nguyễn Trãi, Phường 3, Quận 5, Hồ Chí Minh';return p
        r=GroupPipeline(Model(),Directory('Ảnh cửa hàng Juno')).process_group(items(
          row('Juno - 319 Ấp Bắc, P.5, Tp.Mỹ Tho, Tiền Giang',url='https://juno.vn/image.jpg'),
          row('Juno - 102 Nguyễn Trãi, Phường 3, Quận 5, Hồ Chí Minh',url='https://juno.vn/image.jpg')))
        self.assertEqual([x['approve'] for x in r],['yes','no'])
        self.assertEqual(r[0]['reason'],'GROUP_BRAND_FALLBACK')
        self.assertFalse(r[0]['checks']['group_decision']['proof']['branch_identified'])

if __name__=='__main__':unittest.main()
