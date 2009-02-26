#include "UFuncOperator.hpp"
#include "Literal.hpp"
#include "Visitor.hpp"

#define PY_ARRAY_UNIQUE_SYMBOL _SRFIT_PY_ARRAY
#define NO_IMPORT_ARRAY
#define PY_UFUNC_UNIQUE_SYMBOL _SRFIT_PY_UFUNC
#define NO_IMPORT_UFUNC

#include <boost/python.hpp>
#include <numpy/arrayobject.h>
#include <numpy/noprefix.h>
#include <numpy/ufuncobject.h>

#include <string>
#include <iostream>

using namespace diffpy::srfit;
namespace bp = boost::python;

namespace
{
// The code below was taken from numpy source. State the proper license for
// this.

void find_array_wrap(PyObject* args, PyObject** output_wrap, int nin, int nout)
{
    // The "+1" is for the optional passed storage array.
    Py_ssize_t maxargs = nin+nout+1; 
    Py_ssize_t nargs;
    int i;
    int np = 0;
    double priority, maxpriority;
    PyObject *with_wrap[maxargs], *wraps[maxargs];
    PyObject *obj, *wrap = NULL;

    nargs = PyTuple_GET_SIZE(args);
    for(i = 0; i < nin; i++) {
        obj = PyTuple_GET_ITEM(args, i);
        if (PyArray_CheckExact(obj) ||  \
            PyArray_IsAnyScalar(obj))
            continue;
        wrap = PyObject_GetAttrString(obj, "__array_wrap__");
        if (wrap) {
            if (PyCallable_Check(wrap)) {
                with_wrap[np] = obj;
                wraps[np] = wrap;
                ++np;
            }
            else {
                Py_DECREF(wrap);
                wrap = NULL;
            }
        }
        else {
            PyErr_Clear();
        }
    }
    if (np >= 2) {
        wrap = wraps[0];
        maxpriority = PyArray_GetPriority(with_wrap[0],
                                          PyArray_SUBTYPE_PRIORITY);
        for(i = 1; i < np; ++i) {
            priority = \
                PyArray_GetPriority(with_wrap[i],
                                    PyArray_SUBTYPE_PRIORITY);
            if (priority > maxpriority) {
                maxpriority = priority;
                Py_DECREF(wrap);
                wrap = wraps[i];
            } else {
                Py_DECREF(wraps[i]);
            }
        }
    }

    /* Here wrap is the wrapping function determined from the
       input arrays (could be NULL).

       For all the output arrays decide what to do.

       1) Use the wrap function determined from the input arrays
       This is the default if the output array is not
       passed in.

       2) Use the __array_wrap__ method of the output object
       passed in. -- this is special cased for
       exact ndarray so that no PyArray_Return is
       done in that case.
    */

    for(i=0; i<nout; i++) {
        int j = nin + i;
        int incref = 1;
        output_wrap[i] = wrap;
        if (j < nargs) {
            obj = PyTuple_GET_ITEM(args, j);
            if (obj == Py_None)
                continue;
            if (PyArray_CheckExact(obj)) {
                output_wrap[i] = Py_None;
            }
            else {
                PyObject *owrap;
                owrap = PyObject_GetAttrString(obj,"__array_wrap__");
                incref = 0;
                if (!(owrap) || !(PyCallable_Check(owrap))) {
                    Py_XDECREF(owrap);
                    owrap = wrap;
                    incref = 1;
                    PyErr_Clear();
                }
                output_wrap[i] = owrap;
            }
        }
        if (incref) {
            Py_XINCREF(output_wrap[i]);
        }
    }

    Py_XDECREF(wrap);
    return;
}

PyObject*
ufunc_generic_call(PyUFuncObject* self, PyObject* args, PyObject* kwds)
{
    Py_ssize_t maxargs = self->nargs + 1;
    int i;
    PyTupleObject *ret;
    PyArrayObject *mps[maxargs];
    PyObject *retobj[maxargs];
    PyObject *wraparr[maxargs];
    PyObject *res;
    int errval;

    bp::object tempf(bp::handle<>(bp::borrowed((PyObject*) self)));

    /*
     * Initialize all array objects to NULL to make cleanup easier
     * if something goes wrong.
     */
    for(i = 0; i < self->nargs; i++) {
        mps[i] = NULL;
    }

    errval = PyUFunc_GenericFunction(self, args, kwds, mps);
    if (errval < 0) {
        for(i = 0; i < self->nargs; i++) {
            PyArray_XDECREF_ERR(mps[i]);
        }
        return NULL;
    }

    for(i = 0; i < self->nin; i++) {
        Py_DECREF(mps[i]);
    }


    /*
     * Use __array_wrap__ on all outputs
     * if present on one of the input arguments.
     * If present for multiple inputs:
     * use __array_wrap__ of input object with largest
     * __array_priority__ (default = 0.0)
     *
     * Exception:  we should not wrap outputs for items already
     * passed in as output-arguments.  These items should either
     * be left unwrapped or wrapped by calling their own __array_wrap__
     * routine.
     *
     * For each output argument, wrap will be either
     * NULL --- call PyArray_Return() -- default if no output arguments given
     * None --- array-object passed in don't call PyArray_Return
     * method --- the __array_wrap__ method to call.
     */
    find_array_wrap(args, wraparr, self->nin, self->nout);

    /* wrap outputs */
    for(i = 0; i < self->nout; i++) {
        int j=self->nin+i;
        PyObject *wrap;

        /*
         * check to see if any UPDATEIFCOPY flags are set
         * which meant that a temporary output was generated
         */
        if (mps[j]->flags & UPDATEIFCOPY) {
            PyObject *old = mps[j]->base;
            /* we want to hang on to this */
            Py_INCREF(old);
            /* should trigger the copyback into old */
            Py_DECREF(mps[j]);
            mps[j] = (PyArrayObject *)old;
        }
        wrap = wraparr[i];
        if (wrap != NULL) {
            if (wrap == Py_None) {
                Py_DECREF(wrap);
                retobj[i] = (PyObject *)mps[j];
                continue;
            }
            res = PyObject_CallFunction(wrap, "O(OOi)",
                                        mps[j], self, args, i);
            if (res == NULL && \
                PyErr_ExceptionMatches(PyExc_TypeError)) {
                PyErr_Clear();
                res = PyObject_CallFunctionObjArgs(wrap,
                                                   mps[j],
                                                   NULL);
            }
            Py_DECREF(wrap);
            if (res == NULL) {
                goto fail;
            }
            else if (res == Py_None) {
                Py_DECREF(res);
            }
            else {
                Py_DECREF(mps[j]);
                retobj[i] = res;
                continue;
            }
        }
        /* default behavior */
        retobj[i] = PyArray_Return(mps[j]);
    }

    if (self->nout == 1) {
        return retobj[0];
    } else {
        ret = (PyTupleObject *)PyTuple_New(self->nout);
        for(i = 0; i < self->nout; i++) {
            PyTuple_SET_ITEM(ret, i, retobj[i]);
        }
        return (PyObject *)ret;
    }
fail:
    for(i = self->nin; i < self->nargs; i++) {
        Py_XDECREF(mps[i]);
    }
    return NULL;
}

}

UFuncOperator::UFuncOperator() : Operator(), f(0) {};

UFuncOperator::~UFuncOperator() {
    Py_XDECREF(this->f);
};

void
UFuncOperator::setUFunc(bp::object& s, std::string symbol)
{
    this->symbol = symbol;
    this->f = s.ptr();
    Py_INCREF(this->f);
    PyUFuncObject* npyf = (PyUFuncObject*) this->f;
    this->name = npyf->name;
    this->symbol = symbol;
    if( "" == symbol )
    {
        this->symbol = npyf->name;
    }
    this->nin = npyf->nin;
    this->nout = npyf->nout;
}


bp::object
UFuncOperator::callFunction(const bp::object& arglist)
{
    PyObject* args = arglist.ptr();
    PyUFuncObject* npyf = (PyUFuncObject*) this->f;
    PyObject* kwds = NULL;
    //std::cout << "repr " << bp::extract<char*>( arglist.attr("__repr__")() ) 
    //          << std::endl;
    //bp::object tempf(bp::handle<>(bp::borrowed(this->f)));
    //std::cout << "repr " << bp::extract<char*>( tempf.attr("__repr__")() ) 
    //    << std::endl;
    PyObject* retval = ufunc_generic_call(npyf, args, kwds);

    if( !retval )
    {
        PyErr_SetString(PyExc_ValueError, "Cannot evalate function");
        bp::throw_error_already_set();
    }
    bp::object obj(bp::handle<>(bp::borrowed(retval)));
    return obj;
}

