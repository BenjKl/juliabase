#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""Helper classes and function for the views that are used for the institute.
It extends :py:mod:`samples.views.form_utils` (in includes all names from it)
with institute specific classes and functions.
"""

from __future__ import absolute_import, unicode_literals
import django.utils.six as six
from django.utils.six.moves import urllib

from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext as _
import django.core.urlresolvers
from django.contrib import messages
from jb_common.utils import is_json_requested, respond_in_json
from samples.views.form_utils import *
from samples import permissions


def edit_depositions(request, deposition_number, form_set, institute_model, edit_url, rename_conservatively=False):
    """This function is the central view for editing, creating, and duplicating for
    any deposition.  The edit functions in the deposition views are wrapper
    functions who provides this function with the specific informations.  If
    `deposition_number` is ``None``, a new depositon is created (possibly by
    duplicating another one).

    :param request: the HTTP request object
    :param deposition_number: the number (=name) or the deposition
    :param form_set: the related formset object for the deposition
    :param institute_model: the related Database model
    :param edit_url: the location of the edit template
    :param rename_conservatively: If ``True``, rename only provisional and
        cleaning process names.  This is used by the Large Sputter deposition.
        See the ``new_names`` parameter in
        `samples.views.split_after_deposition.forms_from_database` for how this
        is achieved

    :type request: QueryDict
    :type deposition_number: unicode or NoneType
    :type form_set: FormSet
    :type institute_model: `samples.models.depositions.Deposition`
    :type edit_url: unicode
    :type rename_conservatively: bool

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    permissions.assert_can_add_edit_physical_process(request.user, form_set.deposition, institute_model)
    if request.method == "POST":
        form_set.from_post_data(request.POST)
        deposition = form_set.save_to_database()
        if deposition:
            if form_set.remove_from_my_samples_form and \
                    form_set.remove_from_my_samples_form.cleaned_data["remove_from_my_samples"]:
                utils.remove_samples_from_my_samples(deposition.samples.all(), form_set.user)
            next_view = next_view_kwargs = None
            query_string = ""
            newly_finished = deposition.finished and (not form_set.deposition or getattr(form_set, "unfinished", False))
            if newly_finished:
                rename = False
                new_names = {}
                if rename_conservatively:
                    for sample in deposition.samples.all():
                        name_format = utils.sample_name_format(sample.name)
                        if name_format == "provisional" or name_format == "old" and sample.name[2] in ["N", "V"]:
                            rename = True
                        elif name_format == "old":
                            new_names[sample.id] = sample.name
                else:
                    rename = True
                if rename:
                    next_view = "samples.views.split_after_deposition.split_and_rename_after_deposition"
                    next_view_kwargs = {"deposition_number": deposition.number}
                    query_string = urllib.parse.urlencode([("new-name-{0}".format(id_), new_name)
                                                           for id_, new_name in new_names.items()])
            elif not deposition.finished:
                next_view, __, next_view_kwargs = django.core.urlresolvers.resolve(request.path)
                next_view_kwargs["deposition_number"] = deposition.number
            if deposition_number:
                message = _("Deposition {number} was successfully changed in the database."). \
                    format(number=deposition.number)
                json_response = True
            else:
                message = _("Deposition {number} was successfully added to the database.").format(number=deposition.number)
                json_response = deposition.number
            return utils.successful_response(request, message, next_view, next_view_kwargs or {}, query_string,
                                             forced=next_view is not None, json_response=json_response)
        else:
            messages.error(request, _("The deposition was not saved due to incorrect or missing data."))
    else:
        form_set.from_database(request.GET)
    institute_model_name = utils.capitalize_first_letter(institute_model._meta.verbose_name)
    title = _("Edit {name} “{number}”").format(name=institute_model_name, number=deposition_number) if deposition_number \
        else _("Add {name}").format(name=institute_model._meta.verbose_name)
    title = utils.capitalize_first_letter(title)
    context_dict = {"title": title}
    context_dict.update(form_set.get_context_dict())
    return render(request, edit_url, context_dict)


def show_depositions(request, deposition_number, institute_model):
    """Show an existing new deposision.  You must be an operator of the deposition
    *or* be able to view one of the samples affected by this deposition in order to
    be allowed to view it.

    :param request: the current HTTP Request object
    :param deposition_number: the number (=name) or the deposition
    :param institute_model: the related Database model

    :type request: HttpRequest
    :type deposition_number: unicode
    :type institute_model: `samples.models.depositions.Deposition`

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    deposition = get_object_or_404(institute_model, number=deposition_number)
    permissions.assert_can_view_physical_process(request.user, deposition)
    if is_json_requested(request):
        return respond_in_json(deposition.get_data())
    template_context = {"title": _("{name} “{number}”").format(name=institute_model._meta.verbose_name,
                                                               number=deposition.number),
                        "samples": deposition.samples.all(),
                        "process": deposition}
    template_context.update(utils.digest_process(deposition, request.user))
    return render(request, "samples/show_process.html", template_context)


def measurement_is_referentially_valid(measurement_form, sample_form, measurement_number, institute_model):
    """Test whether the forms are consistent with each other and with the
    database.  In particular, it tests whether the sample is still “alive” at
    the time of the measurement.

    :param measurement_form: a bound measurement form
    :param sample_form: a bound sample selection form
    :param measurement_number: The number of the measurement to be edited.  If
        it is ``None``, a new measurement is added to the database.
    :param institute_model: the related Database model

    :type measurement_form: `samples.views.form_utils.ProcessForm`
    :type sample_form: `SampleForm`
    :type measurement_number: unicode
    :type institute_model: `samples.models.common.Process`

    :return:
      whether the forms are consistent with each other and the database

    :rtype: bool
    """
    referentially_valid = True
    if measurement_form.is_valid():
        number = measurement_form.cleaned_data.get("number")
        number = number and six.text_type(number)
        if number is not None and (measurement_number is None or number != measurement_number) and \
                institute_model.objects.filter(number=number).exists():
            measurement_form.add_error("number", _("This number is already in use."))
            referentially_valid = False
        if sample_form.is_valid() and dead_samples([sample_form.cleaned_data["sample"]],
                                                    measurement_form.cleaned_data["timestamp"]):
            measurement_form.add_error("timestamp", _("Sample is already dead at this time."))
            referentially_valid = False
    else:
        referentially_valid = False
    return referentially_valid


def three_digits(number):
    """
    :param number: the number of the deposition (only the number after the
        deposition system letter)

    :type number: int

    :return:
      The number filled with leading zeros so that it has at least three
      digits.

    :rtype: unicode
    """
    return "{0:03}".format(number)


class SampleForm(forms.Form):
    """Form for the sample selection field.  You can only select *one* sample
    per process (in contrast to depositions).
    """
    _ = ugettext_lazy
    sample = SampleField(label=capfirst(_("sample")))

    def __init__(self, user, process_instance, preset_sample, *args, **kwargs):
        """I only set the selection of samples to the
        current user's “My Samples”.

        :param user: the current user
        :param process_instance: the process instance to be edited, or ``None`` if
            a new is about to be created
        :param preset_sample: the sample to which the process should be
            appended when creating a new process; see
            `utils.extract_preset_sample`

        :type user: django.contrib.auth.models.User
        :type process_instance: `samples.models.common.Process`
        :type preset_sample: `samples.models.Sample`
        """
        super(SampleForm, self).__init__(*args, **kwargs)
        samples = list(user.my_samples.all())
        if process_instance:
            sample = process_instance.samples.get()
            samples.append(sample)
            self.fields["sample"].initial = sample.pk
        if preset_sample:
            samples.append(preset_sample)
            self.fields["sample"].initial = preset_sample.pk
        self.fields["sample"].set_samples(samples, user)


deposition_number_pattern = re.compile("\d\d[A-Z]-\d{3,4}$")
def clean_deposition_number_field(value, letter):
    """Checks wheter a deposition number given by the user in a form is a
    valid one.  Note that it does not check whether a deposition with this
    number already exists in the database.  It just checks the syntax of the
    number.

    :param value: the deposition number entered by the user
    :param letter: the single uppercase letter denoting the deposition system;
        it may also be a list containing multiple possibily letters

    :type value: unicode
    :type letter: unicode or list of unicode

    :return:
      the original `value` (unchanged)

    :rtype: unicode

    :raises ValidationError: if the deposition number was not a valid deposition
        number
    """
    if not deposition_number_pattern.match(value):
        # Translators: “YY” is year, “L” is letter, and “NNN” is number
        raise ValidationError(_("Invalid deposition number.  It must be of the form YYL-NNN."))
    if isinstance(letter, list):
        if value[2] not in letter:
            raise ValidationError(_("The deposition letter must be an uppercase “{letter}”.").format(
                    letter=", ".join(letter)))
    else:
        if value[2] != letter:
            raise ValidationError(_("The deposition letter must be an uppercase “{letter}”.").format(letter=letter))
    return value