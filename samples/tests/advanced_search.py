#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


from __future__ import absolute_import

from django.test import TestCase
from django.test.client import Client


class AdvancedSearchTest(TestCase):
    fixtures = ["test_samples"]
    urls = "samples.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="testuser", password="12345")

    def test_empty_search(self):
        response = self.client.get("/advanced_search")
        self.assertContains(response, u"No search was performed yet.", status_code=200)
        response = self.client.get("/advanced_search",
                                   {"_model": "Sample", "_old_model": "Sample", "name": "",
                                    "currently_responsible_person": "", "current_location": "", "purpose": "",
                                    "tags": "", "topic_main": "", "1-_model": "TestPhysicalProcess",
                                    "1-_old_model": ""})
        self.assertContains(response, u"No search was performed yet.", status_code=200)

    def test_simple_search(self):
        response = self.client.get(
            "/advanced_search",
            {"_model": "Sample", "_old_model": "Sample", "name": "", "currently_responsible_person": "",
             "current_location": "", "purpose": "", "tags": "", "topic_main": "", "1-_model": "TestPhysicalProcess",
             "1-_old_model": "TestPhysicalProcess", "1-operator": "", "1-external_operator": "", "1-timestamp_min": "",
             "1-timestamp_max": "", "1-comments": "", "1-finished": "", "1-number_min": "", "1-number_max": "",
             "1-raw_datafile": "", "1-evaluated_datafile": "", "1-apparatus": "", "1-1-_model": "", "1-1-_old_model": "",
             "2-_model": "", "2-_old_model": ""})
        self.assertContains(response, u"10-TB-first", status_code=200)
        self.assertContains(response, u"10-TB-third")
        self.assertNotContains(response, u"10-TB-second")


class AdvancedSearchWithReducedPermissionsTest(TestCase):
    fixtures = ["test_samples"]
    urls = "samples.tests.urls"

    def setUp(self):
        self.client = Client()
        assert self.client.login(username="testuser2", password="12345")

    def test_simple_search(self):
        response = self.client.get(
            "/advanced_search",
            {"_model": "Sample", "_old_model": "Sample", "name": "", "currently_responsible_person": "",
             "current_location": "", "purpose": "", "tags": "", "topic_main": "", "1-_model": "TestPhysicalProcess",
             "1-_old_model": "TestPhysicalProcess", "1-operator": "", "1-external_operator": "", "1-timestamp_min": "",
             "1-timestamp_max": "", "1-comments": "", "1-finished": "", "1-number_min": "", "1-number_max": "",
             "1-raw_datafile": "", "1-evaluated_datafile": "", "1-apparatus": "", "1-1-_model": "", "1-1-_old_model": "",
             "2-_model": "", "2-_old_model": ""})
        self.assertContains(response, u"10-TB-first", status_code=200)
        self.assertNotContains(response, u"10-TB-third")
        self.assertNotContains(response, u"10-TB-second")
