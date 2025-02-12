import os

from angrmanagement.ui.views import CodeView
from angr.analyses.decompiler.structured_codegen import DummyStructuredCodeGenerator
from angr import knowledge_plugins
import angr

from binsync.common.controller import *
from binsync.data import StackOffsetType, Function, FunctionHeader
import binsync


class AngrBinSyncController(BinSyncController):
    """
    The class used for all pushing/pulling and merging based actions with BinSync data.
    This class is resposible for handling callbacks that are done by changes from the local user
    and responsible for running a thread to get new changes from other users.
    """

    def __init__(self, workspace):
        super(AngrBinSyncController, self).__init__()
        self._workspace = workspace
        self._instance = workspace.instance

    def binary_hash(self) -> str:
        return self._instance.project.loader.main_object.md5.hex()

    def active_context(self):
        curr_view = self._workspace.view_manager.current_tab
        if not curr_view:
            return None

        try:
            func = curr_view.function
        except NotImplementedError:
            return None

        if func is None or func.am_obj is None:
            return None

        return binsync.data.Function(func.addr, header=FunctionHeader(func.name, func.addr))

    #
    # Display Fillers
    #

    def fill_struct(self, struct_name, user=None, state=None):
        pass

    @init_checker
    @make_ro_state
    def fill_function(self, func_addr, user=None, state=None):
        func = self._instance.kb.functions[func_addr]

        # re-decompile a function if needed
        decompilation = self.decompile_function(func)

        _func: binsync.data.Function = self.pull_function(func.addr, user=user)
        if _func is None:
            # the function does not exist for that user's state
            return False

        # ==== Function Name ==== #
        func.name = _func.name
        decompilation.cfunc.name = _func.name
        decompilation.cfunc.demangled_name = _func.name

        # ==== Comments ==== #
        for addr, cmt in self.pull_comments(func_addr).items():
            if not cmt or not cmt.comment:
                continue

            if cmt.decompiled:
                pos = decompilation.map_addr_to_pos.get_nearest_pos(addr)
                corrected_addr = decompilation.map_pos_to_addr.get_node(pos).tags['ins_addr']
                decompilation.stmt_comments[corrected_addr] = cmt.comment
            else:
                self._instance.kb.comments[cmt.addr] = cmt.comment

        # ==== Stack Vars ==== #
        sync_vars = self.pull_stack_variables(func.addr, user=user)
        for offset, sync_var in sync_vars.items():
            code_var = AngrBinSyncController.find_stack_var_in_codegen(decompilation, offset)
            if code_var:
                code_var.name = sync_var.name
                code_var.renamed = True

        decompilation.regenerate_text()
        self.decompile_function(func, refresh_gui=True)

    #
    #   Pushers
    #

    @init_checker
    @make_state
    def push_stack_variable(self, func_addr, offset, name, type_, size_, user=None, state=None):
        sync_var = binsync.data.StackVariable(offset, StackOffsetType.ANGR, name, type_, size_, func_addr)
        return state.set_stack_variable(sync_var, offset, func_addr)

    @init_checker
    @make_state
    def push_comment(self, addr, cmt, decompiled, user=None, state=None):
        func_addr = self._get_func_addr_from_addr(addr)
        sync_cmt = binsync.data.Comment(addr, cmt, func_addr=func_addr, decompiled=decompiled)
        return state.set_comment(sync_cmt)

    @init_checker
    @make_state
    def push_function_header(self, func_addr, new_name, user=None, state=None):
        func_header = binsync.data.FunctionHeader(new_name, func_addr)
        return state.set_function_header(func_header)

    #
    #   Utils
    #

    def decompile_function(self, func, refresh_gui=False):
        # check for known decompilation
        available = self._instance.kb.structured_code.available_flavors(func.addr)
        should_decompile = False
        if 'pseudocode' not in available:
            should_decompile = True
        else:
            cached = self._instance.kb.structured_code[(func.addr, 'pseudocode')]
            if isinstance(cached, DummyStructuredCodeGenerator):
                should_decompile = True

        if should_decompile:
            # recover direct pseudocode
            self._instance.project.analyses.Decompiler(func, flavor='pseudocode')

            # attempt to get source code if its available
            source_root = None
            if self._instance.original_binary_path:
                source_root = os.path.dirname(self._instance.original_binary_path)
            self._instance.project.analyses.ImportSourceCode(func, flavor='source', source_root=source_root)

        # grab newly cached pseudocode
        decomp = self._instance.kb.structured_code[(func.addr, 'pseudocode')].codegen
        if refresh_gui:
            # refresh all views
            self._workspace.reload()

            # re-decompile current view to cause a refresh
            current_tab = self._workspace.view_manager.current_tab
            if isinstance(current_tab, CodeView) and current_tab.function == func:
                self._workspace.decompile_current_function()

        return decomp

    @staticmethod
    def find_stack_var_in_codegen(decompilation, stack_offset: int) -> Optional[angr.sim_variable.SimStackVariable]:
        for var in decompilation.cfunc.variable_manager._unified_variables:
            if hasattr(var, "offset") and var.offset == stack_offset:
                return var

        return None

    @staticmethod
    def func_insn_addrs(func: angr.knowledge_plugins.Function):
        insn_addrs = set()
        for block in func.blocks:
            insn_addrs.update(block.instruction_addrs)

        return insn_addrs

    def _get_func_addr_from_addr(self, addr):
        try:
            func_addr = self._workspace.instance.kb.cfgs.get_most_accurate()\
                .get_any_node(addr, anyaddr=True)\
                .function_address
        except AttributeError:
            func_addr = None

        return func_addr
