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

class ModelingError(ValueError):
    pass

def model(session, targets, *, block=True, combined_templates=False, custom_script=None,
    dist_restraints=None, executable_location=None, fast=False, het_preserve=False,
    hydrogens=False, license_key=None, num_models=5, show_gui=True, temp_path=None,
    thorough_opt=False, water_preserve=False):
    """
    Generate comparitive models for the target sequences.

    Arguments:
    session
        current session
    targets
        list of (alignment, sequence) tuples.  Each sequence will be modelled.
    block
        If True, wait for modelling job to finish before returning and return list of
        (opened) models.  Otherwise return immediately.  Also see 'show_gui' option.
    combined_templates
        If True, all associated chains are used together as templates to generate a single set
        of models for the target sequence.  If False, the associated chains are used individually
        to generate chains in the resulting models (i.e. the models will be multimers).
    custom_script
        If provided, the location of a custom Modeller script to use instead of the
        one we would otherwise generate.  Only used when executing locally.
    dist_restraints
        If provided, the location of a file containing additional distance restraints
    executable_location
        If provided, the path to the locally installed Modeller executable.  If not
        provided, use the web service.
    fast
        Whether to use fast but crude generation of models
    het_preserve
        Whether to preserve HET atoms in generated models
    hydrogens
        Whether to generate models with hydrogen atoms
    license_key
        Modeller license key.  If not provided, try to use settings to find one.
    num_models
        Number of models to generate for each template sequence
    show_gui
        If True, show user interface for Modeller results (if ChimeraX is in gui mode).
    temp_path
        If provided, folder to use for temporary files
    thorough_opt
        Whether to perform thorough optimization
    water_preserve
        Whether to preserve water in generated models
    """

    from chimerax.core.errors import LimitationError
    template_info = []
    for alignment, orig_target in targets:
        if not alignment.associations:
            raise ModelingError("Alignment %s has no associated chains to use as templates."
                % alignment.ident)
        # Copy the target sequence, changing name to conform to Modeller limitations
        from .common import modeller_copy
        target = modeller_copy(orig_target)
        if combined_templates:
            target_templates = []
            template_info.append((target, target_templates))
        for chain, aseq in alignment.associations.items():
            if len(chain.chain_id) > 1:
                raise LimitationError(
                    "Modeller cannot handle templates with multi-character chain IDs")
            if not combined_templates:
                target_templates = []
                template_info.append((target, target_templates))
            target_templates.append((regularized_seq(aseq, chain), chain, aseq.match_maps[chain]))
    if not combined_templates:
        template_info.sort(key=lambda x: (x[1][0][1].structure.id, x[1][0][1].chain_id))

    from .common import write_modeller_scripts
    script_path, config_path, temp_dir = write_modeller_scripts(license_key, num_models, het_preserve,
        water_preserve, hydrogens, fast, None, custom_script, temp_path, thorough_opt, dist_restraints)

    input_file_map = []

    # collate the template info in series of strings that can be joined with '/'
    target_strings = []
    templates_strings = []
    from chimerax.atomic.pdb import standard_polymeric_res_names as std_res_names
    for target, templates_info in template_info:
        target_seq = target.characters
        target_strings.append(target_seq)
        target_template_strings = []
        templates_strings.append(target_template_strings)
        accum_water_het = ""
        for template, chain, match_map in templates_info:
            # match_map has the chain-to-aseq original match map
            # missing positions have already been changed to '-' in template
            end = chain.existing_residues[-1]
            template_string = template.characters + accum_water_het
            accum = ""
            if not het_preserve and not water_preserve:
                target_template_strings.append(template_string)
                continue
            # add het/water characters and get proper end residue
            before_end = True
            for r in chain.structure.residues:
                if before_end:
                    before_end = r != end
                    continue
                if r.chain_id != chain.chain_id or (r.chain and r.chain != chain):
                    break
                end = r
                if water_preserve and r.name in r.standard_water_names \
                or het_preserve and r.name not in std_res_names:
                    char = '.'
                else:
                    char = '-'
                target_seq += char
                template_string += char
                accum_ += '-'
            accum_water_het += accum
            for i, tts in enumerate(target_template_strings):
                target_template_strings[i] = tts + accum
            target_template_strings.append(template_string)
    # Insert/append all-'-' strings so that each template is in it's own line
    insertions = []
    appendings = []
    for i in range(len(templates_strings)):
        insertions.append([])
        appendings.append([])
    for i, target_template_strings in enumerate(templates_strings):
        line_to_add = '-' * len(target_template_strings[0])
        for appending in appendings[:i]:
            appending.append(line_to_add)
        for insertion in insertions[i+1:]:
            insertion.append(line_to_add)

    # form the sequences to be written out as a PIR
    pir_seqs = []
    from chimerax.atomic import Sequence
    structures_to_save = set()
    for i, tmpl_strs in enumerate(templates_strings):
        for j, tmpl_str in enumerate(tmpl_strs):
            chain = template_info[i][1][j][1]
            pir_template = Sequence(name=chain_save_name(chain))
            pir_seqs.append(pir_template)
            pir_template.description = "structure:%s:FIRST:%s:+%d:%s::::" % (
                structure_save_name(chain.structure),
                chain.chain_id, len(tmpl_str) - tmpl_str.count('-'), chain.chain_id)
            structures_to_save.add(chain.structure)
            full_line = tmpl_str
            prefix = '/'.join(insertions[i])
            if prefix:
                full_line = prefix + '/' + full_line
            suffix = '/'.join(appendings[i])
            if suffix:
                full_line = full_line + '/' + suffix
            pir_template.characters = full_line
    pir_target = Sequence(name=template_info[0][0].name)
    # now for something completely different...
    # write the namelist.dat file, target seq name on first line, templates on remaining lines
    import os.path
    name_file = os.path.join(temp_dir.name, "namelist.dat")
    input_file_map.append(("namelist.dat", "text_file", name_file))
    with open(name_file, 'w') as f:
        print(pir_target.name, file=f)
        for template_seq in pir_seqs:
            print(template_seq.name, file=f)
    # carry on...
    pir_seqs.append(pir_target)
    pir_target.description = "sequence:%s:.:.:.:.::::" % pir_target.name
    pir_target.characters = '/'.join(target_strings)
    pir_file = os.path.join(temp_dir.name, "alignment.ali")
    aln = session.alignments.new_alignment(pir_seqs, False, auto_associate=False)
    aln.save(pir_file, format_name="pir")
    session.alignments.destroy_alignment(aln)
    input_file_map.append(("alignment.ali", "text_file", pir_file))

    config_name = os.path.basename(config_path)
    input_file_map.append((config_name, "text_file", config_path))

    # save structure files
    import os
    struct_dir = os.path.join(temp_dir.name, "template_struc")
    if not os.path.exists(struct_dir):
        try:
            os.mkdir(struct_dir, mode=0o755)
        except FileExistsError:
            pass
    from chimerax.atomic.pdb import save_pdb
    for structure in structures_to_save:
        base_name = structure_save_name(structure) + '.pdb'
        pdb_file_name = os.path.join(struct_dir, base_name)
        input_file_map.append((base_name, "text_file",  pdb_file_name))
        ATOM_res_names = structure.in_seq_hets
        ATOM_res_names.update(std_res_names)
        save_pdb(session, pdb_file_name, models=[structure], polymeric_res_names=ATOM_res_names)
        delattr(structure, 'in_seq_hets')

    if executable_location is None:
        if custom_script is not None:
            raise LimitationError("Custom Modeller scripts only supported when executing locally")
        if dist_restraints is not None:
            raise LimitationError("Distance restraints only supported when executing locally")
        if thorough_opt:
            session.logger.warning("Thorough optimization only supported when executing locally")
        job_runner = ModellerWebService(session, [info[1][0][1] for info in template_info], num_models,
            pir_target.name, input_file_map, config_name, targets, show_gui)
    else:
        #TODO: job_runner = ModellerLocal(...)
        from chimerax.core.errors import LimitationError
        raise LimitationError("Local Modeller execution not yet implemented")
        # a custom script [only used when executing locally] needs to be copied into the tmp dir...
        if os.path.exists(script_path) \
        and os.path.normpath(temp_dir.name) != os.path.normpath(os.path.dirname(script_path)):
            import shutil
            shutil.copy(script_path, temp_dir.name)

    return job_runner.run(block=block)

def regularized_seq(aseq, chain):
    mmap = aseq.match_maps[chain]
    from .common import modeller_copy
    rseq = modeller_copy(aseq)
    rseq.description = "structure:" + chain_save_name(chain)
    seq_chars = list(rseq.characters)
    from chimerax.atomic import Sequence
    from chimerax.atomic.pdb import standard_polymeric_res_names as std_res_names
    in_seq_hets = []
    for ungapped in range(len(aseq.ungapped())):
        gapped = aseq.ungapped_to_gapped(ungapped)
        if ungapped not in mmap:
            seq_chars[gapped] = '-'
        else:
            r = mmap[ungapped]
            if r.name not in std_res_names:
                in_seq_hets.append(r)
                seq_chars[gapped] = '.'
            else:
                seq_chars[gapped] = Sequence.rname3to1(mmap[ungapped].name)
    s = chain.structure
    het_set = getattr(s, 'in_seq_hets', set())
    het_set.update(in_seq_hets)
    s.in_seq_hets = het_set
    rseq.characters = "".join(seq_chars)
    return rseq

def structure_save_name(s):
    return s.name.replace(':', '_').replace(' ', '_') + "_" + s.id_string

def chain_save_name(chain):
    return structure_save_name(chain.structure) + '/' + chain.chain_id.replace(' ', '_')

from .common import RunModeller
class ModellerWebService(RunModeller):

    def __init__(self, session, align_chains, num_models, target_seq_name, input_file_map, config_name,
            targets, show_gui):

        super().__init__(session, align_chains, num_models, target_seq_name, targets, show_gui)
        self.input_file_map = input_file_map
        self.config_name = config_name

        self.job = None

    def run(self, *, block=False):
        if block:
            from chimerax.core.errors import LimitationError
            raise LimitationError("Blocking web service Modeller jobs not yet implemented")
        self.job = ModellerJob(self.session, self, self.config_name, self.input_file_map)

    def take_snapshot(self, session, flags):
        """For session/scene saving"""
        return {
            'base data': super().take_snapshot(session, flags),
            'input_file_map': self.input_file_map,
            'config_name': self.config_name,
        }

    @staticmethod
    def restore_snapshot(session, data):
        inst = ModellerWebService(session, None, None, None, data['input_file_map'], data['config_name'],
            None, None)
        inst.set_state_from_snapshot(data['base data'])

from chimerax.core.webservices.opal_job import OpalJob
class ModellerJob(OpalJob):

    OPAL_SERVICE = "Modeller9v8Service"
    SESSION_SAVE = True

    def __init__(self, session, caller, command, input_file_map):
        super().__init__(session)
        self.caller = caller
        self.start(self.OPAL_SERVICE, command, input_file_map=input_file_map)

    def on_finish(self):
        logger = self.session.logger
        logger.info("Modeller job ID %s finished" % self.job_id)
        if not self.exited_normally():
            err = self.get_file("stderr.txt")
            if self.fail_callback:
                self.fail_callback(self, err)
                return
            if err:
                raise RuntimeError("Modeller failure; standard error:\n" + err.decode("utf-8"))
            else:
                raise RuntimeError("Modeller failure with no error output")
        try:
            model_info = self.get_file("ok_models.dat")
        except KeyError:
            raise RuntimeError("No output models from Modeller")
        try:
            stdout = self.get_file("stdout.txt")
        except KeyError:
            raise RuntimeError("No standard output from Modeller job")
        def get_pdb_model(fname):
            from io import StringIO
            try:
                pdb_text = self.get_file(fname)
            except KeyError:
                raise RuntimeError("Could not find Modeller out PDB %s on server" % fname)
            from chimerax.atomic.pdb import open_pdb
            return open_pdb(self.session, StringIO(pdb_text.decode('utf-8')), fname)[0][0]
        self.caller.process_ok_models(model_info.decode('utf-8'), stdout.decode('utf-8'), get_pdb_model)
        self.caller = None
        return
        #TODO: actually do the stuff in _parseOKModels instead of the below
        from chimerax.atomic.pdb import open_pdb
        from io import StringIO
        structures = []
        for line in model_info.decode('utf-8').split('\n'):
            if '.pdb' in line:
                pdb_fname, ga341, zdope = line.split()
                structures.append(open_pdb(self.session,
                    StringIO(self.get_file(pdb_fname).decode('utf-8')), pdb_fname)[0][0])
                structures[-1].ga341 = ga341
                structures[-1].zdope = zdope
        self.session.models.add(structures)
