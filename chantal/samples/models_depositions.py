#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Models for depositions.  This includes the deposition models themselves as
well as models for layers.  Additionally, there are miscellaneous models like
the one to 6-chamber deposition channels.

:type default_location_of_deposited_samples: dict mapping `Deposition` to
  string.
"""

import django.contrib.auth.models
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib import admin
import django.core.urlresolvers
from django.utils.http import urlquote, urlquote_plus
from django.db import models
from chantal.samples.models_common import Process
from chantal.samples import permissions
from chantal.samples.csv_common import CSVNode, CSVItem

default_location_of_deposited_samples = {}
u"""Dictionary mapping process classes to strings which contain the default
location where samples can be found after this process has been performed.
This is used in
`samples.views.split_after_deposition.GlobalNewDataForm.__init__`.
"""


class Deposition(Process):
    u"""The base class for deposition processes.  Note that, like `Process`,
    this must never be instantiated.  Instead, derive the concrete deposition
    class from it.

    Every derived class, if it has sub-objects which resemble layers, must
    implement them as a class derived from `Layer`, with a ``ForeignKey`` field
    pointing to the deposition class with ``relative_name="layers"``.  In other
    words, ``instance.layers.all()`` must work if ``instance`` is an instance
    of your deposition class.
    """
    number = models.CharField(_(u"deposition number"), max_length=15, unique=True, db_index=True)

    class Meta:
        verbose_name = _(u"deposition")
        verbose_name_plural = _(u"depositions")

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.main.show_deposition", [urlquote(self.number, safe="")])

    def __unicode__(self):
        _ = ugettext
        return _(u"deposition %s") % self.number

    def get_data(self):
        # See `Process.get_data` for the documentation.
        _ = ugettext
        csv_node = super(Deposition, self).get_data()
        csv_node.items.append(CSVItem(_(u"number"), self.number, "deposition"))
        csv_node.children = [layer.get_data() for layer in self.layers.all()]
        return csv_node


class SixChamberDeposition(Deposition):
    u"""6-chamber depositions.
    """
    carrier = models.CharField(_(u"carrier"), max_length=10, blank=True)

    class Meta:
        verbose_name = _(u"6-chamber deposition")
        verbose_name_plural = _(u"6-chamber depositions")
        _ = lambda x: x
        permissions = (("add_edit_six_chamber_deposition", _("Can create and edit 6-chamber depositions")),)

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.six_chamber_deposition.show", [urlquote(self.number, safe="")])

    def get_additional_template_context(self, process_context):
        u"""This method is called e.g. when the process list for a sample is
        being constructed.  It returns a dict with additional fields that are
        supposed to be given to the templates.

        ``"edit_url"`` and ``"duplicate_url"`` are somewhat special here
        because they are processed by the *outer* template (the one rendering
        the sample or sample series).  Other keys are just passed to the
        process template itself.  See also
        `samples.views.utils.ResultContext.digest_process` for further
        information.

        :Parameters:
          - `process_context`: the context of this process is for example the
            current sample, the requesting user, and maybe further info that is
            needed by the process to know what further things must be passed to
            the displaying templates (sample(-series) and process templates).

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        if permissions.has_permission_to_add_edit_physical_process(process_context.user, self):
            return {"edit_url": django.core.urlresolvers.reverse("edit_6-chamber_deposition",
                                                                 kwargs={"deposition_number": self.number}),
                    "duplicate_url": "%s?copy_from=%s" % (django.core.urlresolvers.reverse("add_6-chamber_deposition"),
                                                          urlquote_plus(self.number))}
        else:
            return {}

    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  This is the URL, and a short text used for labeling it.  This
        starts with a capital letter, and it is not ended by a full stop.  For
        example, it may be ``u"Add 6-chamber deposition"``.

        This method marks the current class as a so-called physical process.
        This implies that it also must have an “add-edit” permission.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_6-chamber_deposition")

default_location_of_deposited_samples[SixChamberDeposition] = _(u"6-chamber deposition lab")
admin.site.register(SixChamberDeposition)


class Layer(models.Model):
    u"""This is an abstract base model for deposition layers.  Now, this is the
    first *real* abstract model here.  It is abstract because it can never
    occur in a model relationship.  It just ensures that every layer has a
    number, because at least the MyLayers infrastructure relies on this.  (See
    for example `views.six_chamber_deposition.FormSet.__change_structure`,
    after ``if my_layer:``.)

    Note that the above is slightly untrue for cluster tool layers because they
    must be polymorphic.  There, I need a *concret* base class for all layer
    models, derived from this one.  However, I consider this a rim case.  But
    this is debatable: Maybe it's cleaner to make this class concrete.  The
    only drawback would be that in order to access the layer attributes, one
    would have to visit the layer instance explicitly with e.g.

    ::

        six_chamber_deposition.layers.all()[0].six_chamber_layer.temperature

    Every class derived from this model must point to their deposition with
    ``related_name="layers"``.  See also `Deposition`.  Additionally, the
    ``Meta`` class should contain::

        class Meta(Layer.Meta):
            unique_together = ("deposition", "number")
    """
    number = models.IntegerField(_(u"layer number"))

    class Meta:
        abstract = True
        ordering = ["number"]
        verbose_name = _(u"layer")
        verbose_name_plural = _(u"layers")

    def get_data(self):
        u"""Extract the data of this layer as a CSV node with a list of
        key–value pairs, ready to be used for the CSV table export.  See the
        `chantal.samples.views.csv_export` module for all the glory details.

        :Return:
          a node for building a CSV tree

        :rtype: `chantal.samples.csv_common.CSVNode`
        """
        _ = ugettext
        csv_node = CSVNode(self, _(u"layer %d") % self.number)
        csv_node.items = [CSVItem(_(u"number"), unicode(self.number), "layer")]
        return csv_node


class AllGases(models.Model):
    u"""Abstract base model with all gas types that are used in the institute.
    This comes handy if you want to add all these fields to a layer model.
    Just add this class to its list of parent classes.
    """
    sih4 = models.DecimalField(u"SiH₄", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    h2 = models.DecimalField(u"H₂", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    ph3_sih4 = models.DecimalField(_(u"2% PH₃ in SiH₄"), max_digits=5, decimal_places=2, help_text=_(u"in sccm"),
                                   null=True, blank=True)
    tmb_he = models.DecimalField(_(u"1% TMB in He"), max_digits=5, decimal_places=2, help_text=_(u"in sccm"),
                                 null=True, blank=True)
    b2h6_h2 = models.DecimalField(_(u"5ppm B₂H₆ in H₂"), max_digits=5, decimal_places=2, help_text=_(u"in sccm"),
                                  null=True, blank=True)
    ch4 = models.DecimalField(u"CH₄", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    co2 = models.DecimalField(u"CO₂", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    geh4 = models.DecimalField(u"GeH₄", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    ar = models.DecimalField(u"Ar", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    si2h6 = models.DecimalField(u"Si₂H₆", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    ph3_h2 = models.DecimalField(_(u"10 ppm PH₃ in H₂"), max_digits=5, decimal_places=2, help_text=_(u"in sccm"),
                                 null=True, blank=True)

    class Meta:
        abstract = True


six_chamber_chamber_choices = (
    ("#1", "#1"),
    ("#2", "#2"),
    ("#3", "#3"),
    ("#4", "#4"),
    ("#5", "#5"),
    ("#6", "#6"))
u"""Contains all possible choices for `SixChamberLayer.chamber`.
"""

class SixChamberLayer(Layer):
    u"""One layer in a 6-chamber deposition.

    FixMe: Maybe `chamber` should become optional, too?
    """
    deposition = models.ForeignKey(SixChamberDeposition, related_name="layers", verbose_name=_(u"deposition"))
    chamber = models.CharField(_(u"chamber"), max_length=5, choices=six_chamber_chamber_choices)
    pressure = models.CharField(_(u"deposition pressure"), max_length=15, help_text=_(u"with unit"), blank=True)
    time = models.CharField(_(u"deposition time"), max_length=9, help_text=_(u"format HH:MM:SS"), blank=True)
    substrate_electrode_distance = \
        models.DecimalField(_(u"substrate–electrode distance"), null=True, blank=True, max_digits=4,
                            decimal_places=1, help_text=_(u"in mm"))
    comments = models.TextField(_(u"comments"), blank=True)
    transfer_in_chamber = models.CharField(_(u"transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_(u"pre-heat"), max_length=9, blank=True, help_text=_(u"format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_(u"gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.CharField(_(u"pressure of gas pre-heat"), max_length=15, blank=True,
                                             help_text=_(u"with unit"))
    gas_pre_heat_time = models.CharField(_(u"time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_(u"format HH:MM:SS"))
    heating_temperature = models.IntegerField(_(u"heating temperature"), help_text=_(u"in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_(u"transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    plasma_start_power = models.DecimalField(_(u"plasma start power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                             help_text=_(u"in W"))
    plasma_start_with_carrier = models.BooleanField(_(u"plasma start with carrier"), default=False, null=True, blank=True)
    deposition_frequency = models.DecimalField(_(u"deposition frequency"), max_digits=5, decimal_places=2,
                                               null=True, blank=True, help_text=_(u"in MHz"))
    deposition_power = models.DecimalField(_(u"deposition power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text=_(u"in W"))
    base_pressure = models.FloatField(_(u"base pressure"), help_text=_(u"in Torr"), null=True, blank=True)

    class Meta(Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _(u"6-chamber layer")
        verbose_name_plural = _(u"6-chamber layers")

    def __unicode__(self):
        _ = ugettext
        return _(u"layer %(number)d of %(deposition)s") % {"number": self.number, "deposition": self.deposition}

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        _ = ugettext
        csv_node = super(SixChamberLayer, self).get_data()
        csv_node.items.extend([CSVItem(_(u"chamber"), self.get_chamber_display()),
                               CSVItem(u"p", self.pressure),
                               CSVItem(_(u"time"), self.time),
                               CSVItem(_(u"electr. dist./mm"), self.substrate_electrode_distance),
                               CSVItem(_(u"transfer in the chamber"), self.transfer_in_chamber),
                               CSVItem(_(u"pre-heat"), self.pre_heat),
                               CSVItem(_(u"gas of gas pre-heat"), self.gas_pre_heat_gas),
                               CSVItem(_(u"pressure of gas pre-heat"), self.gas_pre_heat_pressure),
                               CSVItem(_(u"time of gas pre-heat"), self.gas_pre_heat_time),
                               CSVItem(u"T/℃", self.heating_temperature),
                               CSVItem(_(u"transfer out of the chamber"), self.transfer_out_of_chamber),
                               CSVItem(_("P_start/W"), self.plasma_start_power),
                               CSVItem(_(u"plasma start with carrier"),
                                       _(u"yes") if self.plasma_start_with_carrier else _(u"no")),
                               CSVItem(u"f/MHz", self.deposition_frequency),
                               CSVItem(u"P/W", self.deposition_power),
                               CSVItem(_(u"p_base/Torr"), self.base_pressure),
                               CSVItem(_(u"comments"), self.comments)])
        flow_rates = {}
        for channel in self.channels.all():
            flow_rates[channel.gas] = unicode(channel.flow_rate)
        gas_names = dict(six_chamber_gas_choices)
        for gas_name in gas_names:
            csv_node.items.append(CSVItem(unicode(gas_names[gas_name]) + u" " + _(u"(in sccm)"),
                                          flow_rates.get(gas_name, u"")))
        return csv_node

admin.site.register(SixChamberLayer)


six_chamber_gas_choices = (
    ("SiH4", u"SiH₄"),
    ("H2", u"H₂"),
    ("PH3+SiH4", _(u"2% PH₃ in SiH₄")),
    ("TMB", _(u"1% TMB in He")),
    ("B2H6", _(u"5ppm B₂H₆ in H₂")),
    ("CH4", u"CH₄"),
    ("CO2", u"CO₂"),
    ("GeH4", u"GeH₄"),
    ("Ar", u"Ar"),
    ("Si2H6", u"Si₂H₆"),
    ("PH3", _(u"10 ppm PH₃ in H₂")))
u"""Contains all possible choices for `SixChamberChannel.gas`.
"""

class SixChamberChannel(models.Model):
    u"""One channel of a certain layer in a 6-chamber deposition.
    """
    number = models.IntegerField(_(u"channel"))
    layer = models.ForeignKey(SixChamberLayer, related_name="channels", verbose_name=_(u"layer"))
    gas = models.CharField(_(u"gas and dilution"), max_length=30, choices=six_chamber_gas_choices)
    flow_rate = models.DecimalField(_(u"flow rate"), max_digits=5, decimal_places=2, help_text=_(u"in sccm"))

    class Meta:
        verbose_name = _(u"6-chamber channel")
        verbose_name_plural = _(u"6-chamber channels")
        unique_together = ("layer", "number")
        ordering = ["number"]

    def __unicode__(self):
        _ = ugettext
        return _(u"channel %(number)d of %(layer)s") % {"number": self.number, "layer": self.layer}

admin.site.register(SixChamberChannel)


class LargeAreaDeposition(Deposition):
    u"""Large-area depositions.
    """

    class Meta:
        verbose_name = _(u"large-area deposition")
        verbose_name_plural = _(u"large-area depositions")
        _ = lambda x: x
        permissions = (("add_edit_large_area_deposition", _("Can create and edit large-area depositions")),)

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.large_area_deposition.show", [urlquote(self.number, safe="")])

    def get_additional_template_context(self, process_context):
        u"""See `SixChamberDeposition.get_additional_template_context`.

        :Parameters:
          - `process_context`: the context of this process

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        if permissions.has_permission_to_add_edit_physical_process(process_context.user, self):
            return {"edit_url": django.core.urlresolvers.reverse("edit_large-area_deposition",
                                                                 kwargs={"deposition_number": self.number}),
                    "duplicate_url": "%s?copy_from=%s" % (django.core.urlresolvers.reverse("add_large-area_deposition"),
                                                          urlquote_plus(self.number))}
        else:
            return {}

    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_large-area_deposition")

    @classmethod
    def get_lab_notebook_data(cls, year, month):
        depositions = cls.get_lab_notebook_context(year, month)["processes"]
        data = CSVNode(_(u"lab notebook for %s") % cls._meta.verbose_name_plural)
        for deposition in depositions:
            for layer in deposition.layers.all():
                data.children.append(layer.get_data())
                data.children[-1].descriptive_name = u""
        return data

default_location_of_deposited_samples[SixChamberDeposition] = _(u"large-area deposition lab")
admin.site.register(LargeAreaDeposition)


large_area_layer_type_choices = (
    ("p", "p"),
    ("i", "i"),
    ("n", "n"),
)
large_area_station_choices = (
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
)
large_area_hf_frequency_choices = (
    ("13.56", u"13.56"),
    ("27.12", u"27.12"),
    ("40.68", u"40.68"),
)
# FixMe: should this really be made translatable?
large_area_electrode_choices = (
    ("NN large PC1", _(u"NN large PC1")),
    ("NN large PC2", _(u"NN large PC2")),
    ("NN large PC3", _(u"NN large PC3")),
    ("NN small 1", _(u"NN small 1")),
    ("NN small 2", _(u"NN small 2")),
    ("NN40 large PC1", _(u"NN40 large PC1")),
    ("NN40 large PC2", _(u"NN40 large PC2")),
)

class LargeAreaLayer(Layer):
    u"""One layer in a large-area deposition.

    *Important*: Numbers of large-area layers are the numbers after the “L-”
    because they must be ordinary integers!  This means that all layers of a
    deposition must be in the same calendar year, oh well …
    """
    deposition = models.ForeignKey(LargeAreaDeposition, related_name="layers", verbose_name=_(u"deposition"))
    date = models.DateField(_(u"date"))
    layer_type = models.CharField(_(u"layer type"), max_length=2, choices=large_area_layer_type_choices)
    station = models.CharField(_(u"station"), max_length=2, choices=large_area_station_choices)
    sih4 = models.DecimalField(_(u"SiH₄"), max_digits=5, decimal_places=2, help_text=_(u"in sccm"))
    h2 = models.DecimalField(_(u"H₂"), max_digits=5, decimal_places=1, help_text=_(u"in sccm"))
    tmb = models.DecimalField(u"TMB", max_digits=5, decimal_places=2, help_text=_(u"in sccm"), null=True, blank=True)
    ch4 = models.DecimalField(u"CH₄", max_digits=3, decimal_places=1, help_text=_(u"in sccm"), null=True, blank=True)
    co2 = models.DecimalField(u"CO₂", max_digits=4, decimal_places=1, help_text=_(u"in sccm"), null=True, blank=True)
    ph3 = models.DecimalField(u"PH₃", max_digits=3, decimal_places=1, help_text=_(u"in sccm"), null=True, blank=True)
    power = models.DecimalField(_(u"power"), max_digits=5, decimal_places=1, help_text=_(u"in W"))
    pressure = models.DecimalField(_(u"pressure"), max_digits=3, decimal_places=1, help_text=_(u"in Torr"))
    temperature = models.DecimalField(_(u"temperature"), max_digits=4, decimal_places=1, help_text=_(u"in ℃"))
    hf_frequency = models.DecimalField(_(u"HF frequency"), max_digits=5, decimal_places=2,
                                       choices=large_area_hf_frequency_choices, help_text=_(u"in MHz"))
    time = models.IntegerField(_(u"time"), help_text=_(u"in sec"))
    dc_bias = models.DecimalField(_(u"DC bias"), max_digits=3, decimal_places=1, help_text=_(u"in V"), null=True, blank=True)
    electrode = models.CharField(_(u"electrode"), max_length=30, choices=large_area_electrode_choices)
    electrodes_distance = models.DecimalField(_(u"electrodes distance"), max_digits=4, decimal_places=1,
                                               help_text=_(u"in mm"))

    class Meta(Layer.Meta):
        verbose_name = _(u"large-area layer")
        verbose_name_plural = _(u"large-area layers")

    def __unicode__(self):
        _ = ugettext
        return _(u"layer %(number)d of %(deposition)s") % {"number": self.number, "deposition": self.deposition}

    def get_data(self):
        # See `Layer.get_data` for the documentation.
        _ = ugettext
        csv_node = super(LargeAreaLayer, self).get_data()
        silane_normalized = 0.6 * float(self.sih4)
        silane_concentration = silane_normalized / (silane_normalized + float(self.h2)) * 100
        csv_node.items.extend([CSVItem(_(u"date"), self.date),
                               CSVItem(_(u"layer type"), self.get_layer_type_display()),
                               CSVItem(_(u"station"), self.get_station_display()),
                               CSVItem(u"SiH₄/sccm", self.sih4),
                               CSVItem(u"H₂/sccm", self.h2),
                               CSVItem(u"TMB/sccm", self.tmb),
                               CSVItem(u"CH₄/sccm", self.ch4),
                               CSVItem(u"CO₂/sccm", self.co2),
                               CSVItem(u"PH₃/sccm", self.ph3),
                               CSVItem(u"SC/%", u"%5.2f" % silane_concentration),
                               CSVItem(u"P/W", self.power),
                               CSVItem(u"p/Torr", self.pressure),
                               CSVItem(u"T/℃", self.temperature),
                               CSVItem(u"f_HF/MHz", self.hf_frequency),
                               CSVItem(_(u"time/s"), self.time),
                               CSVItem(_(u"DC bias/V"), self.dc_bias),
                               CSVItem(_(u"electrode"), self.get_electrode_display()),
                               CSVItem(_(u"elec. dist./mm"), self.electrodes_distance)])
        return csv_node

admin.site.register(LargeAreaLayer)


class SmallClusterToolDeposition(Deposition):
    u"""Small (old) cluster tool depositions.
    """
    carrier = models.CharField(_(u"carrier"), max_length=10, blank=True)

    class Meta:
        verbose_name = _(u"small cluster tool deposition")
        verbose_name_plural = _(u"small cluster tool depositions")
        _ = lambda x: x
        permissions = (("add_edit_small_cluster_tool_deposition", _("Can create and edit small cluster tool depositions")),)

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.small_cluster_tool_deposition.show", [urlquote(self.number, safe="")])

    def get_additional_template_context(self, process_context):
        u"""See `SixChamberDeposition.get_additional_template_context`.

        :Parameters:
          - `process_context`: the context of this process

        :type process_context: `views.utils.ProcessContext`

        :Return:
          dict with additional fields that are supposed to be given to the
          templates.

        :rtype: dict mapping str to arbitrary objects
        """
        if permissions.has_permission_to_add_edit_physical_process(process_context.user, self):
            return {"edit_url": django.core.urlresolvers.reverse("edit_small_cluster_tool_deposition",
                                                                 kwargs={"deposition_number": self.number}),
                    "duplicate_url": "%s?copy_from=%s" % (
                    django.core.urlresolvers.reverse("add_small_cluster_tool_deposition"),
                    urlquote_plus(self.number))}
        else:
            return {}

    @classmethod
    def get_add_link(cls):
        u"""Return all you need to generate a link to the “add” view for this
        process.  See `SixChamberDeposition.get_add_link`.

        :Return:
          the full URL to the add page for this process

        :rtype: str
        """
        _ = ugettext
        return django.core.urlresolvers.reverse("add_small_cluster_tool_deposition")

default_location_of_deposited_samples[SmallClusterToolDeposition] = _(u"small cluster tool deposition lab")
admin.site.register(SmallClusterToolDeposition)


class SmallClusterToolLayer(Layer):
    u"""Model for a layer the old, small “cluster tool”.  Note that this is the
    common base class for the actual layer models
    `SmallClusterToolHotwireLayer` and `SmallClusterToolPECVDLayer`.  This is
    *not* an abstract model though because it needs to be back-referenced from
    the deposition.  I need inheritance and polymorphism here because cluster
    tools may have layers with very different fields.
    """
    deposition = models.ForeignKey(SmallClusterToolDeposition, related_name="layers", verbose_name=_(u"deposition"))

    class Meta(Layer.Meta):
        unique_together = ("deposition", "number")
        verbose_name = _(u"small cluster tool layer")
        verbose_name_plural = _(u"small cluster tool layers")

    def __unicode__(self):
        _ = ugettext
        return _(u"layer %(number)d of %(deposition)s") % {"number": self.number, "deposition": self.deposition}


small_cluster_tool_wire_material_choices = (
    ("Rhenium", "Rhenium"),
    ("Tantal", "Tantalum"),
    ("Tungsten", "Tungsten"),
)

class SmallClusterToolHotwireLayer(SmallClusterToolLayer, AllGases):
    u"""Model for a hotwire layer in the small cluster tool.  We have no
    “chamber” field here because there is only one hotwire chamber anyway.
    """
    pressure = models.CharField(_(u"deposition pressure"), max_length=15, help_text=_(u"with unit"), blank=True)
    time = models.CharField(_(u"deposition time"), max_length=9, help_text=_(u"format HH:MM:SS"), blank=True)
    substrate_wire_distance = models.DecimalField(_(u"substrate–wire distance"), null=True, blank=True, max_digits=4,
                                                  decimal_places=1, help_text=_(u"in mm"))
    comments = models.TextField(_(u"comments"), blank=True)
    transfer_in_chamber = models.CharField(_(u"transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_(u"pre-heat"), max_length=9, blank=True, help_text=_(u"format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_(u"gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.CharField(_(u"pressure of gas pre-heat"), max_length=15, blank=True,
                                             help_text=_(u"with unit"))
    gas_pre_heat_time = models.CharField(_(u"time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_(u"format HH:MM:SS"))
    heating_temperature = models.IntegerField(_(u"heating temperature"), help_text=_(u"in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_(u"transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    filament_temperature = models.DecimalField(_(u"filament temperature"), max_digits=5, decimal_places=2,
                                               null=True, blank=True, help_text=_(u"in ℃"))
    current = models.DecimalField(_(u"wire current"), max_digits=6, decimal_places=2, null=True, blank=True,
                                  help_text=_(u"in A"))
    voltage = models.DecimalField(_(u"wire voltage"), max_digits=6, decimal_places=2, null=True, blank=True,
                                  help_text=_(u"in V"))
    wire_material = models.CharField(_(u"wire material"), max_length=20, choices=small_cluster_tool_wire_material_choices)
    base_pressure = models.FloatField(_(u"base pressure"), help_text=_(u"in Torr"), null=True, blank=True)

    class Meta(SmallClusterToolLayer.Meta):
        verbose_name = _(u"small cluster tool hotwire layer")
        verbose_name_plural = _(u"small cluster tool hotwire layers")

admin.site.register(SmallClusterToolHotwireLayer)


small_cluster_tool_pecvd_chamber_choices = (
    ("#1", "#1"),
    ("#2", "#2"),
    ("#3", "#3"),
    )

class SmallClusterToolPECVDLayer(SmallClusterToolLayer, AllGases):
    u"""Model for a PECDV layer in the small cluster tool.
    """
    chamber = models.CharField(_(u"chamber"), max_length=5, choices=small_cluster_tool_pecvd_chamber_choices)
    pressure = models.CharField(_(u"deposition pressure"), max_length=15, help_text=_(u"with unit"), blank=True)
    time = models.CharField(_(u"deposition time"), max_length=9, help_text=_(u"format HH:MM:SS"), blank=True)
    substrate_electrode_distance = \
        models.DecimalField(_(u"substrate–electrode distance"), null=True, blank=True, max_digits=4,
                            decimal_places=1, help_text=_(u"in mm"))
    comments = models.TextField(_(u"comments"), blank=True)
    transfer_in_chamber = models.CharField(_(u"transfer in the chamber"), max_length=10, default="Ar", blank=True)
    pre_heat = models.CharField(_(u"pre-heat"), max_length=9, blank=True, help_text=_(u"format HH:MM:SS"))
    gas_pre_heat_gas = models.CharField(_(u"gas of gas pre-heat"), max_length=10, blank=True)
    gas_pre_heat_pressure = models.CharField(_(u"pressure of gas pre-heat"), max_length=15, blank=True,
                                             help_text=_(u"with unit"))
    gas_pre_heat_time = models.CharField(_(u"time of gas pre-heat"), max_length=15, blank=True,
                                         help_text=_(u"format HH:MM:SS"))
    heating_temperature = models.IntegerField(_(u"heating temperature"), help_text=_(u"in ℃"), null=True, blank=True)
    transfer_out_of_chamber = models.CharField(_(u"transfer out of the chamber"), max_length=10, default="Ar", blank=True)
    plasma_start_power = models.DecimalField(_(u"plasma start power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                             help_text=_(u"in W"))
    plasma_start_with_carrier = models.BooleanField(_(u"plasma start with carrier"), default=False, null=True, blank=True)
    deposition_frequency = models.DecimalField(_(u"deposition frequency"), max_digits=5, decimal_places=2,
                                               null=True, blank=True, help_text=_(u"in MHz"))
    deposition_power = models.DecimalField(_(u"deposition power"), max_digits=6, decimal_places=2, null=True, blank=True,
                                           help_text=_(u"in W"))
    base_pressure = models.FloatField(_(u"base pressure"), help_text=_(u"in Torr"), null=True, blank=True)

    class Meta(SmallClusterToolLayer.Meta):
        verbose_name = _(u"small cluster tool PECVD layer")
        verbose_name_plural = _(u"small cluster tool PECVD layers")

admin.site.register(SmallClusterToolPECVDLayer)
