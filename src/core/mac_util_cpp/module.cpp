#include <iostream>			// use std::cerr for debugging
#include <Python.h>			// use PyObject

#include "setfileicon.h"		// use set_file_icon

namespace Mac_Util_Cpp
{

// ----------------------------------------------------------------------------
//
static struct PyMethodDef mac_util_cpp_methods[] =
{
  /* setfileicon.h */
  {const_cast<char*>("set_file_icon"), (PyCFunction)set_file_icon, METH_VARARGS|METH_KEYWORDS, NULL},

  {NULL, NULL, 0, NULL}
};

struct module_state {
    PyObject *error;
};

#define GETSTATE(m) ((struct module_state*)PyModule_GetState(m))

static int mac_util_cpp_traverse(PyObject *m, visitproc visit, void *arg) {
    Py_VISIT(GETSTATE(m)->error);
    return 0;
}

static int mac_util_cpp_clear(PyObject *m) {
    Py_CLEAR(GETSTATE(m)->error);
    return 0;
}


static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "_mac_util",
        NULL,
        sizeof(struct module_state),
        mac_util_cpp_methods,
        NULL,
        mac_util_cpp_traverse,
        mac_util_cpp_clear,
        NULL
};

// ----------------------------------------------------------------------------
// Initialization routine called by python when module is dynamically loaded.
//
extern "C" PyObject *
PyInit__mac_util(void)
{
    PyObject *module = PyModule_Create(&moduledef);
    
    if (module == NULL)
      return NULL;
    struct module_state *st = GETSTATE(module);

    st->error = PyErr_NewException("_mac_util.Error", NULL, NULL);
    if (st->error == NULL) {
        Py_DECREF(module);
        return NULL;
    }

    return module;
}

}	// Mac_Util_Cpp namespace
