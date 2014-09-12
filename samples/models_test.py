#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

"""Models for testing JuliaBase-Samples.  Never use this code as a starting
point for your own work.  It does not represent best common practises in the
JuliaBase world.  In particular, nothing is translatable here.
"""

from __future__ import unicode_literals

import os.path
from django.db import models
import django.core.urlresolvers
from django.utils.http import urlquote
from django.conf import settings
from jb_common.utils import register_abstract_model
from jb_common import search
from samples import permissions
import samples.models
from samples.models import Sample, PhysicalProcess, Process
from samples.views.shared_utils import read_techplot_file
from samples.data_tree import DataNode, DataItem


apparatus_choices = (
    ("setup1", "Setup #1"),
    ("setup2", "Setup #2")
)

class TestPhysicalProcess(PhysicalProcess):
    """Test model for physical measurements.
    """
    number = models.PositiveIntegerField("measurement number", unique=True, db_index=True)
    raw_datafile = models.CharField("raw data file", max_length=200,
                                    help_text="only the relative path below \"data/\"")
    evaluated_datafile = models.CharField("evaluated data file", max_length=200,
                                          help_text="only the relative path below \"data/\"", blank=True)
    apparatus = models.CharField("apparatus", max_length=15, choices=apparatus_choices, default="setup1")

    class Meta(PhysicalProcess.Meta):
        permissions = (("add_measurement", "Can add test measurements"),
                       ("edit_permissions_for_measurement", "Can edit perms for test measurements"),
                       ("view_every_measurement", "Can view all test measurements"))
        verbose_name = "test measurement"
        verbose_name_plural = "test measurements"
        ordering = ["number"]

    def __unicode__(self):
        return "Test measurement #{number}".format(number=self.number)

    def draw_plot(self, axes, plot_id, filename, for_thumbnail):
        x_values, y_values = read_techplot_file(filename)
        axes.semilogy(x_values, y_values)
        axes.set_xlabel("abscissa")
        axes.set_ylabel("ordinate")

    def get_datafile_name(self, plot_id):
        if self.evaluated_datafile:
            return os.path.join("/mnt/data", self.evaluated_datafile)
        else:
            return os.path.join("/mnt/data", self.raw_datafile)

    def get_plotfile_basename(self, plot_id):
        return ("measurement_for_{0}".format(self.samples.get())).replace("*", "")

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(TestPhysicalProcess, self).get_data()
        data_node.items.append(DataItem("number", self.number))
        data_node.items.append(DataItem("apparatus", self.apparatus))
        data_node.items.append(DataItem("raw data file", self.raw_datafile))
        data_node.items.append(DataItem("evaluated data file", self.evaluated_datafile))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data_for_table_export` for the documentation.
        data_node = super(TestPhysicalProcess, self).get_data_for_table_export()
        data_node.items.append(DataItem("number", self.number))
        data_node.items.append(DataItem("apparatus", self.get_apparatus_display()))
        data_node.items.append(DataItem("raw data file", self.raw_datafile))
        data_node.items.append(DataItem("evaluated data file", self.evaluated_datafile))
        return data_node


class AbstractMeasurement(PhysicalProcess):
    number = models.PositiveIntegerField("number", unique=True, db_index=True)

    class Meta(PhysicalProcess.Meta):
        abstract = True

    def __unicode__(self):
        return "Appararus {apparatus_number} measurement of {sample}".format(apparatus_number=self.get_apparatus_number(),
                                                                              sample=self.samples.get())

    @classmethod
    def get_apparatus_number(cls):
        return {AbstractMeasurementOne: 1, AbstractMeasurementTwo: 2}[cls]

    def get_data(self):
        # See `Process.get_data` for the documentation.
        data_node = super(AbstractMeasurement, self).get_data()
        data_node.items.append(DataItem("number", self.number))
        return data_node

    def get_data_for_table_export(self):
        # See `Process.get_data` for the documentation.
        data_node = super(AbstractMeasurement, self).get_data_for_table_export()
        data_node.items.append(DataItem("number", self.number))
        return data_node

    @classmethod
    def get_search_tree_node(cls):
        if cls != AbstractMeasurement:
            # So that derived classes don't get included into the searchable
            # models in the advanced search
            raise NotImplementedError
        search_fields = [search.TextSearchField(cls, "operator", "username"),
                         search.TextSearchField(cls, "external_operator", "name")]
        search_fields.extend(
            search.convert_fields_to_search_fields(cls, ["timestamp_inaccuracy", "cache_keys", "last_modified"]))
        related_models = {Sample: "samples"}
        return search.AbstractSearchTreeNode(
            Process, related_models, search_fields, [AbstractMeasurementOne, AbstractMeasurementTwo], "apparatus")

register_abstract_model(AbstractMeasurement)


class AbstractMeasurementOne(AbstractMeasurement):

    class Meta(AbstractMeasurement.Meta):
        verbose_name = "Apparatus {apparatus_number} measurement".format(apparatus_number=1)
        verbose_name_plural = "Apparatus {apparatus_number} measurements".format(apparatus_number=1)
        permissions = (("add_abstract_measurement_one", "Can add Apparatus 1 measurements"),
                       ("edit_permissions_for_abstract_measurement_one", "Can edit perms for Apparatus 1 measurements"),
                       ("view_every_abstract_measurement_one", "Can view all Apparatus 1 measurements"))


class AbstractMeasurementTwo(AbstractMeasurement):

    class Meta(AbstractMeasurement.Meta):
        verbose_name = "Apparatus {apparatus_number} measurement".format(apparatus_number=2)
        verbose_name_plural = "Apparatus {apparatus_number} measurements".format(apparatus_number=2)
        permissions = (("add_abstract_measurement_two", "Can add Apparatus 2 measurements"),
                       ("edit_permissions_for_abstract_measurement_two", "Can edit perms for Apparatus 2 measurements"),
                       ("view_every_abstract_measurement_two", "Can view all Apparatus 2 measurements"))
