#!/usr/bin/env python
########################################################################
#
# diffpy.srfit      by DANSE Diffraction group
#                   Simon J. L. Billinge
#                   (c) 2008 Trustees of the Columbia University
#                   in the City of New York.  All rights reserved.
#
# File coded by:    Chris Farrow
#
# See AUTHORS.txt for a list of people who contributed.
# See LICENSE.txt for license information.
#
########################################################################
"""The Calculator for Parameter-aware functions.

Calculator is a functor class for producing a signal from embedded Parameters.
Calculators can store Parameters and ParameterSets, Constraints and
Restraints. Also, the __call__ function can be overloaded to accept external
arguments. This is useful when chaining together pieces of a forward
calculation within a FitContribution. A Calculator can be added to another
RecipeOrganizer with the 'registerCalculator' method.

"""

from numpy import array, asarray

from .parameter import Parameter

from .recipeorganizer import RecipeOrganizer

class Calculator(RecipeOrganizer):
    """Base class for calculators.

    A Calculator organizes Parameters and has a __call__ method that can
    calculate a generic signal.

    Attributes
    args            --  List needed by Generator interface.
    clicker         --  A Clicker instance for recording changes in contained
                        Parameters and RecipeOrganizers.
    name            --  A name for this organizer.
    meta            --  A dictionary of metadata needed by the calculator.
    _constraints    --  A dictionary of Constraints, indexed by the constrained
                        Parameter. Constraints can be added using the
                        'constrain' method.
    _orgdict        --  A dictionary containing the Parameters and
                        RecipeOrganizers indexed by name.
    _parameters     --  A list of parameters that this RecipeOrganizer knows
                        about.
    _restraints     --  A set of Restraints. Restraints can be added using the
                        'restrain' or 'confine' methods.
    _organizers     --  A list of RecipeOrganizers that this RecipeOrganizer
                        knows about.
    _eqfactory      --  A diffpy.srfit.equation.builder.EquationFactory
                        instance that is used to create constraints and
                        restraints from string

    """

    # Make some methods public that were protected
    addParameter = RecipeOrganizer._addParameter
    newParameter = RecipeOrganizer._newParameter
    removeParameter = RecipeOrganizer._removeParameter
    addParameterSet = RecipeOrganizer._addOrganizer
    removeParameterSet = RecipeOrganizer._removeOrganizer

    # Overload me!
    def __call__(self, *args):
        """Calculate something.

        This method must be overloaded. When overloading, you should specify
        the arguments explicitly, or this can be done when adding the
        Calculator to a RecipeOrganizer.

        """
        return 0

# End class Calculator

__id__ = "$Id$"
