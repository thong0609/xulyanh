import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from group_images_server import GroupStore
from approve_tool import CheckError

class GroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'main.csv';self.folder=self.root/'out'
        self.rows=[dict(entity_id=str(i),entity_name='Entity '+str(i),image_url=url,
            page_url='https://source.test/'+str(i),approve=label,mo_ta='Description '+str(i))
            for i,(url,label) in enumerate([('https://image.test/a','no'),('https://image.test/a','yes'),
                ('https://image.test/b',''),('',''),('','')])]
        with self.source.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(self.rows[0]));w.writeheader();w.writerows(self.rows)
        self.before=self.source.read_bytes();self.store=GroupStore(self.source,self.folder)
    def tearDown(self):self.tmp.cleanup()
    def duplicate(self):return next(g for g in self.store.ordered if len(g['indices'])==2)
    def test_multi_selection_applies_multiple_yes_persists_and_leaves_other_groups(self):
        self.rows[2]['image_url']=self.rows[0]['image_url']
        with self.source.open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(self.rows[0]));w.writeheader();w.writerows(self.rows)
        store=GroupStore(self.source,self.folder);group=next(g for g in store.ordered if len(g['indices'])==3)
        before=self.source.read_bytes();store.select(group['id'],[0,2])
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(store.stats()['planned_yes'],2);self.assertEqual(store.stats()['planned_no'],1)
        again=GroupStore(self.source,self.folder)
        self.assertEqual(again.page()['groups'][0]['keep_indices'],[0,2])
        with patch('group_images_server.ROOT',self.root):again.write(True,group['id'])
        self.assertEqual([r['approve'] for r in again.rows],['yes','no','yes','',''])
        with patch('group_images_server.ROOT',self.root):again.write(True,group['id'],all_no=True)
        self.assertEqual([r['approve'] for r in again.rows],['no','no','no','',''])

    def test_multi_selection_validation_and_deselect_last_means_no_changes(self):
        group=self.duplicate()
        for invalid in ([0,2],[0,0],[True],['0'],False):
            with self.assertRaises(CheckError):self.store.select(group['id'],invalid)
        self.store.select(group['id'],[0,1]);self.store.select(group['id'],[])
        self.assertIsNone(self.store.choices[group['id']])
        self.assertEqual(self.store.labelled(),self.rows)
        with self.assertRaises(CheckError):self.store.write(True,group['id'])

    def test_group_counts_blank_urls_independent_and_no_automatic_deletion(self):
        s=self.store.stats();self.assertEqual(s['unique_urls'],4);self.assertEqual(s['excess_records'],1)
        self.assertEqual(self.store.labelled(),self.rows)
    def test_select_persists_without_modifying_source_and_filters_in_original_order(self):
        g=self.duplicate();self.store.select(g['id'],0)
        self.assertEqual(self.source.read_bytes(),self.before)
        again=GroupStore(self.source,self.folder)
        self.assertEqual(len(again.labelled()),5)
        self.assertEqual([r['approve'] for r in again.labelled()],['yes','no','','',''])
        with self.assertRaises(CheckError):again.select(g['id'],2)
    def test_auto_prefers_yes_but_respects_explicit_keep_all(self):
        g=self.duplicate();self.store.auto();self.assertEqual(self.store.choices[g['id']],1)
        self.store.select(g['id'],None);self.store.auto()
        self.assertIsNone(self.store.choices[g['id']]);self.assertEqual(len(self.store.labelled()),5)
    def test_export_preserves_source_and_all_kept_fields(self):
        self.store.select(self.duplicate()['id'],0);report=self.store.write()
        self.assertFalse(report['applied']);self.assertEqual(report['removed'],0);self.assertEqual(report['changed_labels'],2)
        self.assertEqual(self.source.read_bytes(),self.before)
        with Path(report['export']).open(encoding='utf-8-sig',newline='') as f:
            actual=list(csv.DictReader(f))
            self.assertEqual(len(actual),5)
            self.assertEqual([r['approve'] for r in actual],['yes','no','','',''])
            self.assertEqual([{k:v for k,v in r.items() if k!='approve'} for r in actual],
                             [{k:v for k,v in r.items() if k!='approve'} for r in self.rows])
    def test_external_change_blocks_export_and_stale_plan_is_ignored(self):
        self.store.select(self.duplicate()['id'],1)
        self.source.write_bytes(self.before+b'\n')
        with self.assertRaises(CheckError):self.store.write()
        again=GroupStore(self.source,self.folder)
        self.assertFalse(again.choices);self.assertTrue(again.warning)
    def test_apply_changes_only_labels_creates_backup_and_keeps_review_progress(self):
        self.store.select(self.duplicate()['id'],0)
        with patch('group_images_server.ROOT',self.root):report=self.store.write(True)
        self.assertTrue(report['applied'])
        self.assertEqual(Path(report['backup']).read_bytes(),self.before)
        with self.source.open(encoding='utf-8-sig',newline='') as f:
            actual=list(csv.DictReader(f))
            self.assertEqual(len(actual),5)
            self.assertEqual([r['approve'] for r in actual],['yes','no','','',''])
            self.assertEqual([{k:v for k,v in r.items() if k!='approve'} for r in actual],
                             [{k:v for k,v in r.items() if k!='approve'} for r in self.rows])
        self.assertTrue(self.store.choices)
        self.assertEqual(self.store.stats()['duplicate_groups'],1)
        self.assertEqual(self.store.stats()['planned_removed'],0)
        self.assertEqual(self.store.stats()['planned_yes'],1)
        self.assertEqual(self.store.stats()['planned_no'],1)

    def test_apply_one_group_does_not_apply_other_pending_choices(self):
        g=self.duplicate();other=next(g for g in self.store.ordered if g['indices']==[2])
        self.store.select(g['id'],0);self.store.select(other['id'],2)
        with patch('group_images_server.ROOT',self.root):report=self.store.write(True,g['id'])
        self.assertEqual([r['approve'] for r in self.store.rows],['yes','no','','',''])
        self.assertEqual(self.store.choices[other['id']],2)
        self.assertEqual(report['changed_labels'],2)
        self.assertNotIn('export',report)
        with patch('group_images_server.ROOT',self.root):second=self.store.write(True,other['id'])
        self.assertEqual(second['backup'],report['backup'])
        self.assertEqual(len(list((self.root/'backups').glob('*.csv'))),1)
        self.assertEqual([r['approve'] for r in self.store.rows],['yes','no','yes','',''])

    def test_apply_group_requires_selection_and_valid_group(self):
        with self.assertRaises(CheckError):self.store.write(True,self.duplicate()['id'])
        with self.assertRaises(CheckError):self.store.write(True,'unknown')
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_review_filter_uses_csv_labels_not_unapplied_selection(self):
        other=next(g for g in self.store.ordered if g['indices']==[2])
        self.assertEqual(self.store.page(kind='unique',review='pending')['matched'],3)
        self.store.select(other['id'],2)
        self.assertEqual(self.store.page(kind='unique',review='pending')['matched'],3)
        self.assertEqual(self.store.page(kind='unique',review='reviewed')['matched'],0)
        with patch('group_images_server.ROOT',self.root):self.store.write(True,other['id'])
        self.assertEqual(self.store.page(kind='unique',review='pending')['matched'],2)
        self.assertEqual(self.store.page(kind='unique',review='reviewed')['matched'],1)

    def test_one_blank_makes_the_whole_group_pending(self):
        group=self.duplicate()
        self.assertTrue(self.store.is_reviewed(group))
        self.store.rows[0]['approve']=''
        self.assertFalse(self.store.is_reviewed(group))
        self.assertEqual(self.store.page(review='pending')['matched'],1)
        self.assertEqual(self.store.page(review='reviewed')['matched'],0)
        self.store.rows[0]['approve']='no'
        self.assertTrue(self.store.is_reviewed(group))

    def test_all_no_overrides_selected_yes_only_in_requested_group(self):
        g=self.duplicate();other=next(g for g in self.store.ordered if g['indices']==[2])
        self.store.select(g['id'],1);self.store.select(other['id'],2)
        with patch('group_images_server.ROOT',self.root):report=self.store.write(True,g['id'],all_no=True)
        self.assertEqual([r['approve'] for r in self.store.rows],['no','no','','',''])
        self.assertEqual(len(self.store.rows),5)
        self.assertEqual(report['removed'],0)
        self.assertIsNone(self.store.choices[g['id']])
        self.assertEqual(self.store.choices[other['id']],2)
        self.assertTrue(self.store.is_reviewed(g))
        # Exporting other pending choices must not restore the previous yes.
        self.assertEqual([r['approve'] for r in self.store.labelled()][:2],['no','no'])
        self.store.reset()
        with patch('group_images_server.ROOT',self.root):again=self.store.write(True,g['id'],all_no=True)
        self.assertEqual(again['changed_labels'],0)

    def test_pagination_filter_and_reset(self):
        self.assertEqual(self.store.page()['matched'],1)
        self.assertEqual(self.store.page(kind='unique')['matched'],3)
        self.assertEqual(self.store.page(label='yes')['matched'],1)
        self.store.auto();self.assertEqual(self.store.page(review='pending')['matched'],0)
        self.store.reset();self.assertEqual(self.store.page(review='pending')['matched'],0)
        self.assertEqual(self.store.page(review='reviewed')['matched'],1)

if __name__=='__main__':unittest.main()
