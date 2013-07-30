#include "PDB.h"
#include <string.h>

void
PDB::set_type(RecordType t)
{
	if (t == UNKNOWN) {
		// optimize default case (skip memset())
		r_type = t;
		unknown.junk[0] = '\0';
		return;
	}
	memset(this, 0, sizeof *this);
	r_type = t;
	switch (t) {
	  default:
		break;
	  case ATOM:
		atom.occupancy = 1.0;
		break;
	}
}

#ifdef UNPORTED
int
PDB::byteCmp(const PDB &l, const PDB &r)
{
	return memcmp(&l, &r, sizeof (PDB));
}
#endif  // UNPORTED

void
PDB::reset_state()
{
	input_version = 0;
	atom_serial_number = 10000;
	sigatm_serial_number = 10000;
}
