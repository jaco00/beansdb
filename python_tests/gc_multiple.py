#!/usr/bin/env python
# coding:utf-8

import os
import sys
import unittest
from gc_simple import TestGCBase
import glob
import time
from base import BeansdbInstance, TestBeansdbBase, MCStore, check_data_with_key,check_data_hint_integrity

class TestGCMultiple(TestGCBase):

    def setUp(self):
        self._clear_dir()
        self._init_dir()
        self.backend1 = BeansdbInstance(self.data_base_path, 57901, accesslog=False, max_data_size=10)
        # buffer size is 4m, max_data_size set to 10m for data file better reach above 6m
        # turn off accesslog to speed up write

    # only generate keys in sector0
    def _gen_data(self, data, prefix='', loop_num=10 * 1024, sector=0):
        store = MCStore(self.backend1_addr)
        for key in self.backend1.generate_key(prefix=prefix, count=loop_num, sector=sector):
            if not store.set(key, data):
                return self.fail("fail to set %s" % (key))

    def _delete_data(self, prefix='', loop_num=10 * 1024, sector=0):
        store = MCStore(self.backend1_addr)
        for key in self.backend1.generate_key(prefix=prefix, count=loop_num, sector=sector):
            if not store.delete(key):
                return self.fail("fail to delete %s" % (key))

    def _check_data(self, data, prefix='', loop_num=10 * 1024, sector=0):
        store = MCStore(self.backend1_addr)
        for key in self.backend1.generate_key(prefix=prefix, count=loop_num, sector=sector):
            try:
                self.assertEqual(store.get(key), data)
            except Exception, e:
                return self.fail("fail to check key %s: %s" % (key, str(e)))


    def test_gc_multiple_files(self):
        self.backend1.start()
        self._gen_data(1, prefix='group1_', loop_num=16 * 1024)
        #5M data file 1
        self._gen_data(2, prefix='group1_', loop_num=16 * 1024)
        print 'group1'

        self.backend1.stop()
        self.backend1.start()
        print "restarted"

        self._gen_data(1, prefix='group2_', loop_num=16 * 1024)
        self._gen_data(2, prefix='group2_', loop_num=16 * 1024)

        self.backend1.stop()
        self.backend1.start()
        print "restarted"

        #5M data file 2
        # data file 3
        self._gen_data(1, prefix='group3_', loop_num=512)
        self._gen_data(2, prefix='group3_', loop_num=512)

        self._gen_data(1, prefix='group4_', loop_num=16 * 1024, sector=1)
        self._gen_data(2, prefix='group4_', loop_num=16 * 1024, sector=1)

        self.assertEqual(self.backend1.item_count(), 32 * 1024 + 512 + 16 * 1024)

        sector0_exp = os.path.join(self.backend1.db_home, "0/*.data")

        print "sector0 files", glob.glob(sector0_exp)
        self.assertEqual(len(glob.glob(sector0_exp)), 3)

        self.backend1.stop()
        print "test append some junk data to file, simulate incomplete data file got gc"
        with open(os.path.join(self.backend1.db_home, "0/001.data"), 'a') as f:
            f.write("junkdatasdfsdfsdfdfdf")

        buckets_txt_path = os.path.join(self.backend1.db_home, "0/buckets.txt")
        if os.path.exists(buckets_txt_path):
            print "rm", buckets_txt_path
            os.remove(buckets_txt_path)

        self.backend1.start()
        def check_data():
            self._check_data(2, prefix='group1_', loop_num=16 * 1024)
            self._check_data(2, prefix='group2_', loop_num=16 * 1024)
            self._check_data(2, prefix='group3_', loop_num=512)

        time.sleep(1)
        self._start_gc(0, bucket="0")
        print "gc started"
        while True:
            status = self._gc_status()
            if status.find('running') >= 0:
                check_data()
                continue
            elif status == 'success':
                print "done gc"
                break
            elif status == 'fail':
                return self.fail("optimize_stat = fail")
            else:
                self.fail(status)

        self.assertEqual(self.backend1.item_count(), 32 * 1024 + 512 + 16 * 1024)
        check_data()
        for key in self.backend1.generate_key(prefix="group1_", count=2, sector=0):
            print key
            self.assert_(not check_data_with_key(os.path.join(self.backend1.db_home, "0/000.data"), key, ver_=1))
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "0/000.data"), key, ver_=2))
        print "group2 should be not in 000.data, but in 001.data"
        for key in self.backend1.generate_key(prefix="group2_", count=2, sector=0):
            print key
            self.assert_(not check_data_with_key(os.path.join(self.backend1.db_home, "0/000.data"), key))
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "0/001.data"), key, ver_=2))
        print "group4 of bucket 1 should be untouched"
        for key in self.backend1.generate_key(prefix="group4_", count=2, sector=1):
            print key
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "1/000.data"), key, ver_=1))
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "1/000.data"), key, ver_=2))

        print "check data& hint"
        check_data_hint_integrity(self.backend1.db_home, db_depth=self.backend1.db_depth)

class TestGCMultiple2(TestGCBase):

    def setUp(self):
        self._clear_dir()
        self._init_dir()
        self.backend1 = BeansdbInstance(self.data_base_path, 57901, accesslog=False, max_data_size=10, db_depth=2)
        # buffer size is 4m, max_data_size set to 10m for data file better reach above 6m
        # turn off accesslog to speed up write

    # only generate keys in sector0
    def _gen_data(self, data, prefix='', loop_num=10 * 1024, sector=(0, 0)):
        store = MCStore(self.backend1_addr)
        for key in self.backend1.generate_key(prefix=prefix, count=loop_num, sector=sector):
            if not store.set(key, data):
                return self.fail("fail to set %s" % (key))

    def _delete_data(self, prefix='', loop_num=10 * 1024, sector=(0, 0)):
        store = MCStore(self.backend1_addr)
        for key in self.backend1.generate_key(prefix=prefix, count=loop_num, sector=sector):
            if not store.delete(key):
                return self.fail("fail to delete %s" % (key))

    def _check_data(self, data, prefix='', loop_num=10 * 1024, sector=(0, 0)):
        store = MCStore(self.backend1_addr)
        for key in self.backend1.generate_key(prefix=prefix, count=loop_num, sector=sector):
            try:
                self.assertEqual(store.get(key), data)
            except Exception, e:
                return self.fail("fail to check key %s: %s" % (key, str(e)))

    def test_gc_multiple_files(self):
        self.backend1.start()
        self._gen_data(1, prefix='group1_', loop_num=16 * 1024)
        #5M data file 1
        self._gen_data(2, prefix='group1_', loop_num=16 * 1024)
        print 'group1'

        self.backend1.stop()
        self.backend1.start()
        print "restarted"

        self._gen_data(1, prefix='group2_', loop_num=16 * 1024)
        self._gen_data(2, prefix='group2_', loop_num=16 * 1024)

        self.backend1.stop()
        self.backend1.start()
        print "restarted"

        #5M data file 2
        # data file 3
        self._gen_data(1, prefix='group3_', loop_num=512)
        self._gen_data(2, prefix='group3_', loop_num=512)

        self._gen_data(1, prefix='group4_', loop_num=16 * 1024, sector=(1, 0))
        self._gen_data(2, prefix='group4_', loop_num=16 * 1024, sector=(1, 0))

        self._gen_data(1, prefix='group5_', loop_num=16 * 1024, sector=(0, 1))
        self._gen_data(2, prefix='group5_', loop_num=16 * 1024, sector=(0, 1))

        self.assertEqual(self.backend1.item_count(), 64 * 1024 + 512)

        sector00_exp = os.path.join(self.backend1.db_home, "0/0/0*.data")
        sector01_exp = os.path.join(self.backend1.db_home, "0/1/0*.data")
        sector10_exp = os.path.join(self.backend1.db_home, "1/0/0*.data")

        self.assertEqual(len(glob.glob(sector00_exp)), 3)
        self.assertEqual(len(glob.glob(sector01_exp)), 1)
        self.assertEqual(len(glob.glob(sector10_exp)), 1)

        self.backend1.stop()
        def check_data():
            self._check_data(2, prefix='group1_', loop_num=16 * 1024)
            self._check_data(2, prefix='group2_', loop_num=16 * 1024)
            self._check_data(2, prefix='group3_', loop_num=512)



        self.backend1.start()
        self._start_gc(0, bucket="1")
        print "gc @1 started"
        while True:
            status = self._gc_status()
            if status.find('running') >= 0:
                check_data()
                continue
            elif status == 'success':
                print "done gc"
                break
            elif status == 'fail':
                return self.fail("optimize_stat = fail")
            else:
                self.fail(status)
        print "group4 got gc"
        for key in self.backend1.generate_key(prefix="group4_", count=2, sector=(1, 0)):
            print key
            self.assert_(not check_data_with_key(os.path.join(self.backend1.db_home, "1/0/000.data"), key, ver_=1))
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "1/0/000.data"), key, ver_=2))
        print "group1 should be untouched"
        for key in self.backend1.generate_key(prefix="group1_", count=2, sector=(0, 0)):
            print key
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "0/0/000.data"), key, ver_=1))
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "0/0/000.data"), key, ver_=2))


        time.sleep(1)
        self._start_gc(0, bucket="00")
        print "gc @00 started"
        while True:
            status = self._gc_status()
            if status.find('running') >= 0:
                check_data()
                continue
            elif status == 'success':
                print "done gc"
                break
            elif status == 'fail':
                return self.fail("optimize_stat = fail")
            else:
                self.fail(status)

        self.assertEqual(self.backend1.item_count(), 64 * 1024 + 512)
        check_data()
        print "group1 got gc"
        for key in self.backend1.generate_key(prefix="group1_", count=2, sector=(0, 0)):
            print key
            self.assert_(not check_data_with_key(os.path.join(self.backend1.db_home, "0/0/000.data"), key, ver_=1))
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "0/0/000.data"), key, ver_=2))
        print "group2 should be not in 000.data, but in 001.data"
        for key in self.backend1.generate_key(prefix="group2_", count=2, sector=(0, 0)):
            print key
            self.assert_(not check_data_with_key(os.path.join(self.backend1.db_home, "0/0/000.data"), key))
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "0/0/001.data"), key, ver_=2))
        print "group5 of bucket 0/1 should be untouched"
        for key in self.backend1.generate_key(prefix="group5_", count=2, sector=(0, 1)):
            print key
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "0/1/000.data"), key, ver_=1))
            self.assert_(check_data_with_key(os.path.join(self.backend1.db_home, "0/1/000.data"), key, ver_=2))

        print "check data& hint"
        check_data_hint_integrity(self.backend1.db_home, db_depth=self.backend1.db_depth)



if __name__ == '__main__':
    unittest.main()



# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
