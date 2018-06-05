# vim: set expandtab shiftwidth=4 softtabstop=4:

# === UCSF ChimeraX Copyright ===
# Copyright 2016 Regents of the University of California.
# All rights reserved.  This software provided pursuant to a
# license agreement containing restrictions on its disclosure,
# duplication and use.  For details see:
# http://www.rbvi.ucsf.edu/chimerax/docs/licensing.html
# This notice must be embedded in or attached to all copies,
# including partial copies, of the software or any revisions
# or derivations thereof.
# === UCSF ChimeraX Copyright ===

from abc import ABCMeta, abstractmethod

class Option(metaclass=ABCMeta):
    """Base class (and common API) for all options"""

    multiple_value = "-- multiple --"
    read_only = False

    def __init__(self, name, default, callback, *, balloon=None, attr_name=None, **kw):
        """'callback' can be None"""

        # non-empty name overrides any default name
        if name or not hasattr(self, 'name'):
            self.name = name

        if attr_name:
            self.attr_name = attr_name
        else:
            if self.name:
                self.attr_name = self.name
            else:
                self.attr_name = None

        if default != None or not hasattr(self, 'default'):
            self.default = default

        self._make_widget(**kw)

        if balloon or not hasattr(self, 'balloon'):
            self.balloon = balloon
        command_line = False
        if hasattr(self, 'in_class'):
            command_line = self.attr_name and '.' not in self.attr_name
        if self.balloon or command_line:
            balloon = self.balloon if self.balloon else ""
            if command_line:
                attr_balloon = "attribute name: " + self.attr_name
                attr_vals = None
                if hasattr(self, "attr_values_balloon"):
                    attr_balloon += '\n' + self.attr_values_balloon
                elif hasattr(self, 'mapping'):
                    attr_vals = self.mapping.items()
                elif hasattr(self, 'labels') and hasattr(self, 'values'):
                    if not isinstance(BooleanOption) or self.labels != BooleanOption.labels:
                        attr_vals = zip(self.values, self.labels)
                if attr_vals:
                    attr_balloon += '\n'
                    vals_text = "values: "
                    for val, vtext in attr_vals:
                        if vals_text != "values: ":
                            vals_text += ", "
                        vals_text += str(val)
                        vals_text += " " + vtext
                        if len(vals_text) > 32:
                            attr_balloon += vals_text
                            attr_balloon += '\n'
                            vals_text = ""
                    if vals_text:
                        attr_balloon += vals_text
                    else:
                        attr_balloon = attr_balloon[:-1]
                if balloon:
                    balloon += "\n\n"
                balloon += attr_balloon
                self.balloon = balloon

        # prevent showing the default from making a callback...
        self._callback = None
        if self.default is not None:
            self.value = self.default
        self._callback = callback

        self._enabled = True
        if self.read_only:
            self.disable()

    @abstractmethod
    def get(self):
        # return the option's value
        pass

    @abstractmethod
    def set(self, value):
        # set the option's value; should NOT invoke the callback
        pass

    def get_attribute(self, obj):
        if not self.attr_name:
            raise ValueError("No attribute associated with %s" % repr(self))
        fetcher = recurse_getattr if '.' in self.attr_name else getattr
        return fetcher(obj, self.attr_name)

    def set_attribute(self, obj):
        if not self.attr_name:
            raise ValueError("No attribute associated with %s" % repr(self))
        setter = recurse_setattr if '.' in self.attr_name else setattr
        setter(obj, self.attr_name, self.get())

    @abstractmethod
    def set_multiple(self):
        # indicate that the items the option covers have multiple different values
        pass

    def _get_value(self):
        return self.get()

    def _set_value(self, val):
        self.set(val)

    value = property(_get_value, _set_value)

    def enable(self):
        # usually no need to override, since enabling/disabling
        # a Qt widget implicitly does the same for its children
        self.widget.setDisabled(False)

    def disable(self):
        # usually no need to override, since enabling/disabling
        # a Qt widget implicitly does the same for its children
        self.widget.setDisabled(True)

    def make_callback(self):
        # Called (usually by GUI) to propagate changes back to program
        if self._callback:
            self._callback(self)

    @abstractmethod
    def _make_widget(self):
        # create (as self.widget) the widget to display the option value
        pass

def recurse_getattr(obj, attr_name):
    attrs = attr_name.split('.')
    for a in attrs:
        obj = getattr(obj, a)
    return obj

def recurse_setattr(obj, attr_name, val):
    attrs = attr_name.split('.')
    for a in attrs[:-1]:
        obj = getattr(obj, a)
    setattr(obj, attrs[-1], val)

class BooleanOption(Option):
    """Option for true/false values"""

    def get(self):
        return self.widget.isChecked()

    def set(self, value):
        self.widget.setChecked(value)

    def set_multiple(self):
        from PyQt5.QtCore import Qt
        self.widget.setCheckState(Qt.PartiallyChecked)

    def _make_widget(self, **kw):
        from PyQt5.QtWidgets import QCheckBox
        self.widget = QCheckBox(**kw)
        self.widget.clicked.connect(lambda state, s=self: s.make_callback())

class EnumOption(Option):
    """Option for enumerated values"""
    values = ()

    def get(self):
        return self.widget.text()

    def remake_menu(self, labels=None):
        from PyQt5.QtWidgets import QAction
        if labels is None:
            labels = self.values
        menu = self.widget.menu()
        menu.clear()
        for label in labels:
            action = QAction(label, self.widget)
            action.triggered.connect(lambda arg, s=self, lab=label: s._menu_cb(lab))
            menu.addAction(action)

    def set(self, value):
        self.widget.setText(value)

    def set_multiple(self):
        self.widget.setText(self.multiple_value)

    def _make_widget(self, *, display_value=None, **kw):
        from PyQt5.QtWidgets import QPushButton, QMenu
        if display_value is None:
            display_value = self.default
        self.widget = QPushButton(display_value, **kw)
        menu = QMenu()
        self.widget.setMenu(menu)
        self.remake_menu()

    def _menu_cb(self, label):
        self.set(label)
        self.make_callback()

class FloatOption(Option):
    """Option for floating-point values.
       Constructor takes option min/max keywords to specify lower/upper bound values.
       Besides being numeric values, those keyords can also be 'positive' or 'negative'
       respectively, in which case the allowed value can be arbitrarily close to zero but
       cannot be equal to zero.

       'decimal_places' indicates allowable number of digits after the decimal point
       (default: 3).  Values with more digits will be rounded.  If the widget provides
       a means to increment the value (e.g. up/down arrow) then 'step' is how much the
       value will be incremented (default: 10x the smallest value implied by 'decimal_places').
       
       Supports 'preceding_text' and 'trailing_text' keywords for putting text before
       and after the entry widget on the right side of the form"""

    default_minimum = -(2^31)
    default_maximum = 2^31 - 1

    def get(self):
        val = self.spinbox.value()
        if val == 0.0 and self.non_zero:
            step = self.spinbox.singleStep()
            if self.spinbox.minimum() == 0.0:
                val = step
            else:
                val = -step
        return val

    def set(self, value):
        self.spinbox.setSpecialValueText("")
        self.spinbox.setValue(value)

    def set_multiple(self):
        self.spinbox.setSpecialValueText(self.multiple_value)
        self.spinbox.setValue(self.spinbox.minimum())

    def _make_widget(self, min=None, max=None, preceding_text=None, trailing_text=None,
            decimal_places=3, step=None, **kw):
        from PyQt5.QtWidgets import QDoubleSpinBox, QWidget, QHBoxLayout, QLabel
        def compute_bound(bound, default_bound):
            if bound is None:
                return default_bound
            if bound in ('positive', 'negative'):
                return 0.0
            return bound
        self.non_zero = (max == 'negative' or min == 'positive')
        minimum = compute_bound(min, self.default_minimum)
        maximum = compute_bound(max, self.default_maximum)
        self.spinbox = QDoubleSpinBox(**kw)
        self.spinbox.setDecimals(decimal_places)
        if step is None:
            step = 10 ** (0 - (decimal_places-1))
        self.spinbox.setMinimum(minimum)
        self.spinbox.setMaximum(maximum)
        self.spinbox.setSingleStep(step)
        self.spinbox.valueChanged.connect(lambda val, s=self: s.make_callback())
        if not preceding_text and not trailing_text:
            self.widget = self.spinbox
            return
        self.widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(2)
        if preceding_text:
            layout.addWidget(QLabel(preceding_text))
            l = 0
        layout.addWidget(self.spinbox)
        if trailing_text:
            layout.addWidget(QLabel(trailing_text))
            r = 0
        self.widget.setLayout(layout)

class IntOption(Option):
    """Option for integer values.
       Constructor takes option min/max keywords to specify lower/upper bound values.
       
       Supports 'preceding_text' and 'trailing_text' keywords for putting text before
       and after the entry widget on the right side of the form"""

    default_minimum = -(2^31)
    default_maximum = 2^31 - 1

    def get(self):
        return self._spin_box.value()

    def set(self, value):
        self._spin_box.setSpecialValueText("")
        self._spin_box.setValue(value)

    def set_multiple(self):
        self._spin_box.setSpecialValueText(self.multiple_value)
        self._spin_box.setValue(self._spin_box.minimum())

    def _make_widget(self, min=None, max=None, preceding_text=None, trailing_text=None, **kw):
        from PyQt5.QtWidgets import QSpinBox, QWidget, QHBoxLayout, QLabel
        self._spin_box = QSpinBox(**kw)
        self._spin_box.setMinimum(self.default_minimum if min is None else min)
        self._spin_box.setMaximum(self.default_maximum if max is None else max)
        self._spin_box.valueChanged.connect(lambda val, s=self: s.make_callback())
        if not preceding_text and not trailing_text:
            self.widget = self._spin_box
            return
        self.widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(2)
        if preceding_text:
            layout.addWidget(QLabel(preceding_text))
            l = 0
        layout.addWidget(self._spin_box)
        if trailing_text:
            layout.addWidget(QLabel(trailing_text))
            r = 0
        self.widget.setLayout(layout)

class RGBA8Option(Option):
    """Option for rgba colors, returns 8-bit (0-255) rgba values"""

    def get(self):
        return self.widget.color

    def set(self, value):
        """Accepts a wide variety of values, not just rgba"""
        self.widget.color = value

    def set_multiple(self):
        self.widget.color = None

    def _make_widget(self, **kw):
        from ..widgets import MultiColorButton
        self.widget = MultiColorButton(max_size=(16,16), has_alpha_channel=True)
        self.widget.color_changed.connect(lambda c, s=self: s.make_callback())

class RGBAOption(RGBA8Option):
    """Option for rgba colors, returns floating-point (0-1) rgba values"""

    def get(self):
        return [x/255.0 for x in super().get()]

class ColorOption(RGBA8Option):
    """Option for rgba colors"""

    def get(self):
        from chimerax.core.colors import Color
        return Color(rgba=RGBA8Option.get(self))

class OptionalRGBA8Option(Option):
    """Option for 8-bit (0-255) rgba colors, with possibility of None.

    Supports 'initial_color' constructor arg for initializing the color button even when
    the starting value of the option is None (checkbox will be unchecked)
    """

    # default for class
    default_initial_color = [0.75, 0.75, 0.75, 1.0]

    def get(self):
        if self._check_box.isChecked():
            return self._color_button.color
        return None

    def set(self, value):
        """Accepts a wide variety of values, not just rgba"""
        if value is None:
            self._check_box.setChecked(False)
        else:
            self._check_box.setChecked(True)
            self._color_button.color = value

    def set_multiple(self):
        self._check_box.setChecked(True)
        self._color_button.color = None

    def _make_widget(self, **kw):
        from ..widgets import MultiColorButton
        from PyQt5.QtWidgets import QWidget, QCheckBox, QHBoxLayout
        self.widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        self._check_box = cb = QCheckBox()
        cb.clicked.connect(lambda state, s=self: s.make_callback())
        layout.addWidget(cb)
        self._color_button = mcb = MultiColorButton(max_size=(16,16), has_alpha_channel=True)
        mcb.color = kw.get('initial_color', self.default_initial_color)
        mcb.color_changed.connect(lambda c, s=self: s.make_callback())
        layout.addWidget(mcb)
        self.widget.setLayout(layout)

class OptionalRGBAOption(OptionalRGBA8Option):
    """Option for floating-point (0-1) rgba colors, with possibility of None.

    Supports 'initial_color' constructor arg for initializing the color button even when
    the starting value of the option is None (checkbox will be unchecked)
    """

    def get(self):
        rgba8 = super().get()
        if rgba8 is None:
            return None
        return [x/255.0 for x in rgba8]

class OptionalRGBA8PairOption(Option):
    """Like OptionalRGBA8Option, but two checkboxes/colors

    Supports 'initial_colors' constructor arg (2-tuple of colors) for initializing the color buttons
    even when the starting value of the option is (None, None) (checkboxes will be unchecked)
    """

    def get(self):
        return (self._color_button[i].color if self._check_box[i].isChecked() else None
            for i in range(2) )

    def set(self, value):
        """2-tuple.  Accepts a wide variety of values, not just rgba"""
        for i, val in enumerate(value):
            if val is None:
                self._check_box[i].setChecked(False)
            else:
                self._check_box[i].setChecked(True)
                self._color_button[i].color = val

    def set_multiple(self):
        for i in range(2):
            self._check_box[i].setChecked(True)
            self._color_button[i].color = None

    def _make_widget(self, **kw):
        from ..widgets import MultiColorButton
        from PyQt5.QtWidgets import QWidget, QCheckBox, QHBoxLayout, QLabel
        labels = kw.pop('labels', (None, "  "))
        self.widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        self._check_box = []
        self._color_button = []
        for i in range(2):
            label = labels[i]
            if label:
                layout.addWidget(QLabel(label))
            cb = QCheckBox()
            self._check_box.append(cb)
            cb.clicked.connect(lambda state, s=self: s.make_callback())
            layout.addWidget(cb)
            mcb = MultiColorButton(max_size=(16,16), has_alpha_channel=True)
            self._color_button.append(mcb)
            default_color = OptionalRGBA8Option.default_initial_color
            mcb.color = kw.get('initial_colors', (default_color, default_color))[i]
            mcb.color_changed.connect(lambda c, s=self: s.make_callback())
            layout.addWidget(mcb)
        self.widget.setLayout(layout)

class OptionalRGBAPairOption(OptionalRGBA8PairOption):
    """Like OptionalRGBAOption, but two checkboxes/colors

    Supports 'initial_colors' constructor arg (2-tuple of colors) for initializing the color buttons
    even when the starting value of the option is (None, None) (checkboxes will be unchecked)
    """

    def get(self):
        rgba8s = super().get()
        return tuple(None if i is None else [c/255.0 for c in i] for i in rgba8s)

class StringOption(Option):
    """Option for text strings"""

    def get(self):
        return self.widget.text()

    def set(self, value):
        self.widget.setText(value)

    def set_multiple(self):
        self.widget.setText(self.multiple_value)

    def _make_widget(self, **kw):
        from PyQt5.QtWidgets import QLineEdit
        self.widget = QLineEdit(**kw)
        self.widget.editingFinished.connect(lambda s=self: s.make_callback())

class StringIntOption(Option):
    """Option for a string and an int (as a 2-tuple), for something such as host and port"""

    default_minimum = IntOption.default_minimum
    default_maximum = IntOption.default_maximum

    def get(self):
        return (self._line_edit.text(), self._spin_box.value())

    def set(self, value):
        text, integer = value
        self._line_edit.setText(text)
        self._spin_box.setSpecialValueText("")
        self._spin_box.setValue(integer)

    def set_multiple(self):
        self._line_edit.setText(self.multiple_value)
        self._spin_box.setSpecialValueText(self.multiple_value)
        self._spin_box.setValue(self._spin_box.minimum())

    def _make_widget(self, min=None, max=None, string_label=None, int_label=None,
            initial_text_width="10em", **kw):
        """initial_text_width should be a string hold a "stylesheet-friendly"
           value, (e.g. '10em' or '7ch') or None"""
        from PyQt5.QtWidgets import QLineEdit
        self._line_edit = QLineEdit()
        self._line_edit.editingFinished.connect(lambda s=self: s.make_callback())
        if initial_text_width:
            self._line_edit.setStyleSheet("* { width: %s }" % initial_text_width)
        from PyQt5.QtWidgets import QSpinBox, QWidget, QHBoxLayout, QLabel
        self._spin_box = QSpinBox(**kw)
        self._spin_box.setMinimum(self.default_minimum if min is None else min)
        self._spin_box.setMaximum(self.default_maximum if max is None else max)
        self._spin_box.valueChanged.connect(lambda val, s=self: s.make_callback())
        self.widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(2)
        if string_label:
            layout.addWidget(QLabel(string_label))
            l = 0
        layout.addWidget(self._line_edit)
        if int_label:
            layout.addWidget(QLabel(int_label))
            r = 0
        layout.addWidget(self._spin_box)
        self.widget.setLayout(layout)

class HostPortOption(StringIntOption):
    """Option for a host name or address and a TCP port number (as a 2-tuple)"""
    def _make_widget(self, **kw):
        StringIntOption._make_widget(self, min=0, max=65535, string_label="host", int_label="port",             **kw)


class SymbolicEnumOption(EnumOption):
    """Option for enumerated values with symbolic names"""
    values = ()
    labels = ()

    def get(self):
        return self._value

    def remake_menu(self):
        EnumOption.remake_menu(self, labels=self.labels)

    def set(self, value):
        self._value = value
        self.widget.setText(self.labels[list(self.values).index(value)])

    def set_multiple(self):
        self._value = None
        EnumOption.set_multiple(self)

    def make_callback(self):
        label = self.widget.text()
        i = list(self.labels).index(label)
        self._value = self.values[i]
        EnumOption.make_callback(self)

    def _make_widget(self, **kw):
        self._value = self.default
        EnumOption._make_widget(self,
            display_value=self.labels[list(self.values).index(self.default)], **kw)

    def _menu_cb(self, label):
        self.set(self.values[self.labels.index(label)])
        self.make_callback()
