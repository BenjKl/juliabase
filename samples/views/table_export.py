#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Main routines and all views for the data export.  Believe it or not, this is
probably the most complicated thing in JuliaBase.  The problem is that data in
JuliaBase has a tree-like structure, which is completely incompatible with the
table structure needed for CSV export.

The tree
........

The starting point is the `DataNode` tree.  It is the result of a ``get_data``
method call of a sample, sample series, or single process.  The root note of
such a tree represents the instance whose ``get_data`` method was called.

The direct children of the top node are called “row nodes” or “row trees”
because they will form the rows of the table, by being flattened.

Every `DataNode` has not only children, but also key–value items containing the
actual data.  key is str, value is a Python object.  Additionally, it has a
``name`` which denotes the type or class of the `DataNode`.  For example, the
``name`` of a process may be “PDS measurement” or “5-chamber deposition”.

Making the node names unique
............................

The first transformation which is performed is that the names are made unique
for each row tree.  This is necessary to avoid name clashs in column headings.
For this, numbers are appended if two sister nodes share the same ``name``.
Then, the names of ancestor nodes are prepended.  Therefore, the name of a node
may be “6-chamber deposition #1, layer #2”.

Finding column groups and columns
.................................

The next goal is to organise the columns.  For this I need two data structures:
The ``column_groups`` resembles the union of the nodes in all row trees,
without duplicates.  So, the first row tree is walked through, and each of its
nodes is put into the ``column_groups`` list directly.  Then, the next tree is
scanned, but only *new* nodes (i.e., with a so-far unknown ``name``) are added,
and so forth.  I try to make the order within ``column_groups`` senseful,
however in theory, it doesn't matter really.

The second data structure for columns is simply called ``columns``, and it is
built parallely to ``column_groups`` in `build_column_group_list`.  Whenever a
new column groups is added, its keys (from the key–value items or its node) are
appended to the list of columns.  The resulting indices in ``columns`` are
saved in the column group attribute `ColumnGroup.key_indices`.  This is a
dictionary, mapping key names to their index in the ``columns`` list.

The web view
............

Now the user comes into play.  He is presented the column groups and their keys
in a HTML multiple selection widget.  The values are simply the indices in
``columns``.  Therefore, they are the result sent back to the server as a list
of integers.  Duplicates are dropped (they may occur due to shared columns, see
below).

Generating the final table
..........................

The last needed data structure is a list of all rows, generated by
`flatten_tree`.  Every row is represented by a dictionary with str keys being
names of column groups.  They are mapped to another dictionary mapping key
names to values.  This list of rows is generated by `flatten_tree`.

Finally we're ready to generate the table with `generate_table_rows`: For each
row, the list of indices is used to find the value for the respective column by
using the ``columns`` list, which contains a `Column` instance, which is able
to retrieve the final table cell value through the `Column.get_value` method.

This way, the table is represented by a list of rows, and each row a list of
cells.  Every cell item is a Python object.  The zeroth row contains the
headings (unicodes), the zeroth column the labels for the column (e.g., in case
of exporting a sample series, the sample names, also unicodes).

This very simple data structure can be used directly to show a preview table in
HTML, or to create the CSV data by sending it through an instance of an
`csv.writer`.

Making models fit for data export
.................................

In order to get a proper node tree, all involved model instances must have a
``get_data`` method.  This method must return a `DataNode`, which may in turn
be the root of a whole ``DataNode`` subtree.  Additionally, it probably will
append items to the ``items`` list with the values of the database instance's
attributes.  See `DataNode` and `data_tree.DataItem` for further information.
Additionally, the various instances of the ``get_data`` method in various
database model classes will show you how to use it (they are all very
strightforward).
"""

from django.forms.utils import ValidationError
from django.utils.translation import ugettext_lazy as _, ugettext
import django.forms as forms


class ColumnGroup:
    """Class for representing of set of columns in the table output which
    corresponds to one node type in the input tree.  In the output, the column
    groups are arranged next to each other to form the complete table.  The
    user doesn't notice that because the CSV format doesn't allow for visible
    separation (e.g. by vertical lines) between column groups.

    Instances of this class will be in a list returned by
    `build_column_group_list`.  This list serves two purposes: First, it is
    used internally in ``build_column_group_list`` for avoiding inserting a
    node name twice.  And secondly, it is used to create the multi selection
    boxes in the HTML view for the user.

    :ivar name: name of the column group which directly corresponds to the name
      of the respective `DataNode`.  It must never contain a TAB character
      because this is used as a separator in `OldDataForm`.

    :ivar key_indices: dictionary which maps key names to their index in the
      ``columns`` list which is built parallely to the list of
      ``ColumnGroup``.

    :type name: str
    :type key_indices: dict mapping str to int
    """

    def __init__(self, name):
        """Class constructor.

        :param name: the name of the `DataNode` this column group represents

        :type name: str
        """
        self.name = name
        self.key_indices = {}

    def __repr__(self):
        return repr(self.name)

    def __eq__(self, other):
        """Equation operator.  I need this function because in
        `build_column_group_list`, I must be able to test easily whether a
        given column group is contained in a given list.

        :param other: the instance to compare with

        :type other: `ColumnGroup`

        :return:
          whether ``other`` is equal to the current instance

        :rtype: bool
        """
        return self.name == other.name


class Column:
    """Class for one column in the exported table.  The list of ``Column``
    instances is built in `build_column_group_list`.  It contains *all*
    columns, even those that the user doesn't choose for output.  The index in
    this list is stored in the values of `ColumnGroup.key_indices`.

    :ivar column_group_names: List of names of column groups where one can
      expect the key–value pairs for this column.

      Normally, this list contains exactly *one* item because a column points
      to exactly one particular key in one particular column group.  However in
      case of “shared columns”, this is not so simple anymore.  Then, the value
      is in exactly one of the shared columns, so we have to check all of them
      until we find something.  For more information about shared columns, see
      :py:class:`samples.data_tree.DataItem`.

    :ivar key: the pristine name of the key this column points to, i.e. it
      doesn't contain any affixes to make it unambiguous

    :ivar heading: The heading of the column.  Basically, it's the same as
      `key`, however, if this is ambiguous because another key in another
      column groups has the same name, it is made unique by appending ``" {node
      name}"`` to it.
    """

    def __init__(self, column_group_name, key):
        """Class constructor.

        :param column_group_name: the name of the column group this column is
            part of
        :param key: the pristine key name this column corresponds to

        :type column_group_name: str
        :type key: str
        """
        self.column_group_names = [column_group_name]
        self.key = self.heading = key

    def append_name(self, column_group_name):
        """Append the name of a column group with a shared key.  If the
        current instance of ``Column`` is a shared key, you must call this
        method for each other column group which contains this shared key
        (instead of appending a new key to the ``columns`` list in
        `build_column_group_list`).  For more information about shared columns,
        see :py:class:`data_tree.DataItem`.

        :param column_group_name: the name of the column group this column is
            found in as a shared key

        :type column_group_name: str
        """
        self.column_group_names.append(column_group_name)

    def disambig(self):
        """Make the column heading unique.  Normally, the key is used directly
        for the column heading.  However, if the same key name is used in
        another column group, ``disambig_key_names`` calls this method to make
        it unique.
        """
        self.heading = "{0} {{{1}}}".format(self.key, " / ".join(self.column_group_names))

    def get_value(self, row):
        """Return the value of this column in the given row.

        :param row: the row for which the value in this column should be
            determined

        :type row: dict mapping str to dict mapping str to object

        :return:
          the cell value of this column in the given row; ``None`` if the
          respective column group is not available for the given row

        :rtype: object
        """
        for column_group_name in self.column_group_names:
            if column_group_name in row:
                return row[column_group_name][self.key]
        return ""


def build_column_group_list(root):
    """Extract from the ``CVSNode`` tree the column group list and the column
    list.  The column group list can be used to show the user the columns in a
    structured form, and to export the data in ODF or Excel format.  The
    columns are used for any export, ODF, Excel, and CSV.

    :param root: The root node of the ``DataNode`` tree.  It must be a complete
        tree, i.e. the top-level children are considered the row tree.  The
        node names must have been made unambiguous within a row tree already
        using :py:meth:`samples.data_tree.DataNode.find_unambiguous_names`.

    :type root: `DataNode`

    :return:
      the column groups, the column list

    :rtype: list of `ColumnGroup`, list of `Column`
    """

    def walk_row_tree(node, top_level=True):
        """Extract all node names from a ``DataNode`` tree.  This routine calls
        itself recursively to walk through the tree.  Note that the inner order
        of the nodes (e.g. the chronological order of processes) is preserved
        by this method.

        :param node: the root node of the (sub-)tree to be analysed

        :type node: `DataNode`

        :return:
          all node names

        :rtype: list of str
        """
        node.top_level = top_level
        name_list = [node]
        for child in node.children:
            name_list.extend(walk_row_tree(child, top_level=False))
        return name_list

    def disambig_key_names(columns):
        """Helper function for making all column headings unambiguous.  When
        the columns list is complete, and shortly before it is returned by
        ``build_column_group_list``, it is manipulated so that all ``heading``
        attributes of the columns are unique in the whole table.

        Note that this is only interesting for CSV export.  If you export to
        ODF or Excel, there is a cleaner way by using the column groups to
        format the table (vertical lines, multi-column spans in the header
        etc).  So for ODF and Excel export, the ``heading`` attribute is not
        needed but the pristine ``key`` attribute.

        :param columns: the complete list of columns

        :type columns: list of `Column`
        """
        seen = set()
        duplicates = set()
        for column in columns:
            key = column.key
            if key in seen:
                duplicates.add(key)
            else:
                seen.add(key)
        for column in columns:
            if column.key in duplicates:
                column.disambig()
    columns = []
    column_groups = []
    shared_columns = {}
    position = 0
    for row, row_tree in enumerate(root.children):
        for node in walk_row_tree(row_tree):
            if row > 0 and node in column_groups:
                position = column_groups.index(node)
            else:
                name = node.name
                column_group = ColumnGroup(name)
                i = len(columns)
                for item in node.items:
                    if node.top_level and item.origin:
                        shared_key = (item.origin, item.key)
                        if shared_key in shared_columns:
                            column_group.key_indices[item.key] = shared_columns[shared_key]
                            columns[shared_columns[shared_key]].append_name(name)
                            continue
                        else:
                            shared_columns[shared_key] = i
                    column_group.key_indices[item.key] = i
                    columns.append(Column(name, item.key))
                    i += 1
                column_groups.insert(position, column_group)
            position += 1
    disambig_key_names(columns)
    return column_groups, columns


def flatten_tree(root):
    """Walk through a ``DataNode`` tree and convert it to a list of nested
    dictionaries for easy cell value lookup.  The resulting data structure is
    used in :py:meth:`Column.get_value`.

    :param root: The root node of the ``DataNode`` tree.  It must be a complete
        tree, i.e. the top-level children are considered the row tree.  The
        node names must have been made unambiguous within a row tree already
        using `DataNode.find_unambiguous_names`.

    :type root: `samples.data_tree.DataNode`

    :return:
      list of all rows containg a dictionary mapping node names (loosely
      corresponding to column group names) to dictionaries mapping key names to
      cell values

    :rtype: list of dictionary mapping str to dictionary mapping str to str
    """

    def flatten_row_tree(node):
        name_dict = {node.name: dict((item.key, item.value if item.value is not None else "") for item in node.items)}
        for child in node.children:
            name_dict.update(flatten_row_tree(child))
        return name_dict

    return [flatten_row_tree(row) for row in root.children]


def generate_table_rows(flattened_tree, columns, selected_key_indices, label_column, label_column_heading):
    """Generate the final table suited for CSV export and HTML preview.  Note
    that for ODF or Excel output, you should also take the column group list
    into account for better formatting.

    :param flattened_tree: the transformed tree as constructed by
        `flatten_tree`.
    :param columns: list of columns as constructed by `build_column_group_list`
    :param selected_key_indices: list of the column indices which the user
        selected for output
    :param label_column: The values of the first column, which is supposed to
        contain some sort of heading of the respective row.  For example, for a
        sample series table, the rows are the samples of the series, and their
        names are printed in the first column.  Therefore, the length of this
        list must be equal to the number of rows.

        If all elements are empty, no label column is generated.  This is
        interesting for lab notebooks
    :param label_column_heading: Description of the very first column with the
        table row headings.  This is the contents of the top left cell.  For
        example, for a sample series table, it may be ``"sample"`` because the
        rows are the samples of the series, and their names are printed in the
        first column.

    :type flattened_tree: list of dictionary mapping str to dictionary mapping
      str to str
    :type columns: list of `Column`
    :type selected_key_indices: list of int
    :type label_column: list of str
    :type label_column_heading: str

    :return:
      The table as a nested list.  The outer list are the rows, the inner the
      columns.  Each cell is a string.

    :rtype: list of list of object
    """
    generate_label_column = any(label_column)
    head_row = [label_column_heading] if generate_label_column else []
    head_row.extend([str(columns[key_index].heading) for key_index in selected_key_indices])
    table_rows = [head_row]
    for i, row in enumerate(flattened_tree):
        table_row = [label_column[i]] if generate_label_column else []
        for key_index in selected_key_indices:
            table_row.append(columns[key_index].get_value(row))
        table_rows.append(table_row)
    return table_rows


class ColumnGroupsForm(forms.Form):
    """Form for the columns choice.  It has only one field, ``column_groups``,
    the result of which is a set with the selected column group names.
    """
    column_groups = forms.MultipleChoiceField(label=_("Column groups"))

    def __init__(self, column_groups, *args, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", "") + "__"
        super().__init__(*args, **kwargs)
        self.fields["column_groups"].choices = ((column_group.name, column_group.name) for column_group in column_groups)
        self.fields["column_groups"].widget.attrs["size"] = "10"

    def clean_column_groups(self):
        return set(self.cleaned_data["column_groups"])


class ColumnsForm(forms.Form):
    """Form for the columns choice.  It has only one field, ``columns``, the
    result of which is a set with the selected column indices as ints.
    """
    columns = forms.MultipleChoiceField(label=_("Columns"))

    def __init__(self, column_groups, columns, selected_column_groups, *args, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", "") + "__"
        super().__init__(*args, **kwargs)
        self.fields["columns"].choices = \
            ((column_group.name, [(i, columns[i].key) for i in sorted(column_group.key_indices.values())])
             for column_group in column_groups if column_group.name in selected_column_groups)
        self.fields["columns"].widget.attrs["size"] = "10"

    def clean_columns(self):
        try:
            return set(int(i) for i in self.cleaned_data["columns"])
        except ValueError:
            # Untranslable because internal anyway
            raise ValidationError("Invalid number in column indices list")


class OldDataForm(forms.Form):
    """Form which stores the user input of the previous run.  It is not
    intended for user interaction, in fact it is hidden in the HTML.  By
    comparing the user's input with what is stored here, `export` can detect
    whether the user has changed something.
    """
    column_groups = forms.CharField(required=False)
    columns = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        initial = kwargs.pop("initial", {})
        kwargs["prefix"] = kwargs.get("prefix", "") + "__old_data"
        super().__init__(*args, **kwargs)
        if "column_groups" in initial:
            self.fields["column_groups"].initial = "\t".join(column_group for column_group in initial["column_groups"])
        if "columns" in initial:
            self.fields["columns"].initial = " ".join(str(i) for i in initial["columns"])
        for fieldname in ["column_groups", "columns"]:
            attributes = self.fields[fieldname].widget.attrs
            if "class" not in attributes:
                attributes["class"] = "submit-always"
            else:
                if attributes["class"].strip():
                    attributes["class"] += " "
                attributes["class"] += "submit-always"

    def clean_column_groups(self):
        return set(self.cleaned_data["column_groups"].split("\t"))

    def clean_columns(self):
        try:
            return set(int(i) for i in self.cleaned_data["columns"].split())
        except ValueError:
            # Untranslable because internal anyway
            raise ValidationError("Invalid number in column indices list")


class SwitchRowForm(forms.Form):
    """Form for the tick marks before every row in the preview table.  If it
    is checked, the respective row is included into the CSV export.
    """
    active = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", "") + "__"
        super().__init__(*args, **kwargs)


_ = ugettext
