import sys
import traceback
from types import FrameType, TracebackType
from typing import Union, Iterable

from stack_data import style_with_executing_node, Options, Line, FrameInfo, LINE_GAP, Variable, RepeatedFrames


class Formatter:
    def __init__(
            self, *,
            options=Options(),
            pygmented=False,
            show_executing_node=True,
            pygments_formatter_cls=None,
            pygments_formatter_kwargs=None,
            pygments_style="monokai",
            executing_node_modifier="bg:#005080",
            executing_node_underline="^",
            current_line_indicator="-->",
            line_gap_string="(...)",
            show_variables=False,
            use_code_qualname=True,
            show_linenos=True,
            strip_leading_indent=True,
            html=False,
            chain=True,
            collapse_repeated_frames=True,
    ):
        if pygmented and not options.pygments_formatter:
            try:
                import pygments
            except ImportError:
                pass
            else:
                if show_executing_node:
                    pygments_style = style_with_executing_node(
                        pygments_style, executing_node_modifier
                    )

                if pygments_formatter_cls is None:
                    from pygments.formatters.terminal256 import Terminal256Formatter \
                        as pygments_formatter_cls

                options.pygments_formatter = pygments_formatter_cls(
                    style=pygments_style,
                    **pygments_formatter_kwargs or {},
                )

        self.pygmented = pygmented
        self.show_executing_node = show_executing_node
        assert len(executing_node_underline) == 1
        self.executing_node_underline = executing_node_underline
        self.current_line_indicator = current_line_indicator or ""
        self.line_gap_string = line_gap_string
        self.show_variables = show_variables
        self.show_linenos = show_linenos
        self.use_code_qualname = use_code_qualname
        self.strip_leading_indent = strip_leading_indent
        self.html = html
        self.chain = chain
        self.options = options
        self.collapse_repeated_frames = collapse_repeated_frames

    def set_hook(self):
        def excepthook(_etype, evalue, _tb):
            self.print_exception(evalue)

        sys.excepthook = excepthook

    def print_exception(self, e=None, *, file=None):
        if file is None:
            file = sys.stderr
        for line in self.format_exception(e):
            print(line, file=file, end="")

    def format_exception(self, e=None):
        if e is None:
            e = sys.exc_info()[1]

        if self.chain:
            if e.__cause__ is not None:
                yield from self.format_exception(e.__cause__)
                yield traceback._cause_message
            elif (e.__context__ is not None
                  and not e.__suppress_context__):
                yield from self.format_exception(e.__context__)
                yield traceback._context_message

        yield 'Traceback (most recent call last):\n'

        yield from self.format_stack_data(
            FrameInfo.stack_data(
                e.__traceback__,
                self.options,
                collapse_repeated_frames=self.collapse_repeated_frames,
            )
        )

        yield from traceback.format_exception_only(type(e), e)

    def format_stack_data(self, stack: Iterable[Union[FrameInfo, RepeatedFrames]]):
        for item in stack:
            if isinstance(item, FrameInfo):
                yield from self.format_frame(item)
            else:
                return self.format_repeated_frames(item)

    def format_repeated_frames(self, repeated_frames: RepeatedFrames):
        return '    [... skipping similar frames: {}]\n'.format(
            repeated_frames.description
        )

    def format_frame(self, frame: Union[FrameInfo, FrameType, TracebackType]):
        if not isinstance(frame, FrameInfo):
            frame = FrameInfo(frame, self.options)

        yield self.format_frame_header(frame)

        for line in frame.lines:
            if isinstance(line, Line):
                yield self.format_line(line)
            else:
                assert line is LINE_GAP
                yield self.line_gap_string + "\n"

        if self.show_variables:
            yield from self.format_variables(frame)

    def format_frame_header(self, frame_info: FrameInfo):
        return ' File "{frame_info.filename}", line {frame_info.lineno}, in {name}\n'.format(
            frame_info=frame_info,
            name=(
                frame_info.executing.code_qualname()
                if self.use_code_qualname else
                frame_info.code.co_name
            ),
        )

    def format_line(self, line: Line):
        result = ""
        if self.current_line_indicator:
            if line.is_current:
                result = self.current_line_indicator
            else:
                result = " " * len(self.current_line_indicator)
            result += " "

        if self.show_linenos:
            result += "{:4} | ".format(line.lineno)

        result = result or "   "

        prefix = result

        result += line.render(
            pygmented=self.pygmented,
            escape_html=self.html,
            strip_leading_indent=self.strip_leading_indent,
        ) + "\n"

        if self.show_executing_node and not self.pygmented:
            for line_range in line.executing_node_ranges:
                start = line_range.start - line.leading_indent
                end = line_range.end - line.leading_indent
                result += (
                        " " * (start + len(prefix))
                        + self.executing_node_underline * (end - start)
                        + "\n"
                )

        return result

    def format_variables(self, frame_info: FrameInfo):
        for var in sorted(frame_info.variables, key=lambda v: v.name):
            yield self.format_variable(var) + "\n"

    def format_variable(self, var: Variable):
        return "{} = {}".format(
            var.name,
            self.format_variable_value(var.value),
        )

    def format_variable_value(self, value):
        return repr(value)
