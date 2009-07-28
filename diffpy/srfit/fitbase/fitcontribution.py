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
"""FitContribution class. 

FitContributions are generate a residual function for a FitRecipe. A
FitContribution associates an Equation for generating a signal, optionally one
or more ProfileGenerators or Calculators that help in this, and a Profile that
holds the observed and calculated signals.  

See the examples in the documention for how to use a FitContribution.

"""

from numpy import concatenate, sqrt, inf, dot

from diffpy.srfit.equation import Equation
from diffpy.srfit.equation.builder import EquationFactory

from .parameterset import ParameterSet
from .recipeorganizer import equationFromString
from .parameter import ParameterProxy

class FitContribution(ParameterSet):
    """FitContribution class.

    FitContributions organize an Equation that calculates the signal, and a
    Profile that holds the signal. ProfileGenerators and Calculators can be
    used as well.  Contraints and Restraints can be created as part of a
    FitContribution.

    Attributes
    clicker         --  A Clicker instance for recording changes in the
                        Parameters or the residual components.
    name            --  A name for this FitContribution.
    profile         --  A Profile that holds the measured (and calcuated)
                        signal.
    _confclicker    --  A ConfigurationClicker for recording configuration
                        changes, esp.  additions and removal of managed
                        objects.
    _calculators    --  A managed dictionary of Calculators, indexed by name.
    _constraints    --  A dictionary of Constraints, indexed by the constrained
                        Parameter. Constraints can be added using the
                        'constrain' method.
    _generators     --  A managed dictionary of ProfileGenerators.
    _parameters     --  A managed OrderedDict of parameters.
    _restraints     --  A set of Restraints. Restraints can be added using the
                        'restrain' or 'confine' methods.
    _parsets        --  A managed dictionary of ParameterSets.
    _eqfactory      --  A diffpy.srfit.equation.builder.EquationFactory
                        instance that is used to create constraints and
                        restraints from string
    _eq             --  The FitContribution equation that will be optimized.
    _xname          --  The name of of the independent variable from the
                        profile (default None). 
    _yname          --  The name of of the observed profile (default None). 
    _dyname         --  The name of of the uncertainty in the observed profile
                        (default None).
    _resstr         --  The residual equation in string form.

    """

    def __init__(self, name):
        """Initialization."""
        ParameterSet.__init__(self, name)
        self._eq = None
        self._reseq = None
        self.profile = None
        self._xname = None
        self._yname = None
        self._dyname = None

        self._reseqstr = ""

        self._generators = {}
        self._manage(self._generators)
        return
    
    def setProfile(self, profile, xname = None, yname = None, dyname = None):
        """Assign the Profile for this fitcontribution.

        This resets the current residual (see setResidualEquation).
        
        profile --  A Profile that specifies the calculation points and that
                    will store the calculated signal.
        xname   --  The name of the independent variable from the Profile. If
                    this is None (default), then the name specified by the
                    Profile for this parameter will be used.  This variable is
                    usable within the Equation with the specified name.
        yname   --  The name of the observed Profile.  If this is None
                    (default), then the name specified by the Profile for this
                    parametere will be used.  This variable is usable within
                    the Equation with the specified name.
        dyname  --  The name of the uncertainty in the observed Profile. If
                    this is None (default), then the name specified by the
                    Profile for this parametere will be used.  This variable is
                    usable within the Equation with the specified name.

        """
        seteq = self.profile is None

        # Clear previously watched parameters
        if self.profile is not None:
            self.removeParameter(self._orgdict[self._xname])
            self.removeParameter(self._orgdict[self._yname])
            self.removeParameter(self._orgdict[self._dyname])

        # Set the Profile and add its parameters to this organizer.

        self.profile = profile

        if xname is None:
            xname = self.profile.xpar.name
        if yname is None:
            yname = self.profile.ypar.name
        if dyname is None:
            dyname = self.profile.dypar.name

        self._xname = xname
        self._yname = yname
        self._dyname = dyname

        xpar = ParameterProxy(self._xname, self.profile.xpar)
        ypar = ParameterProxy(self._yname, self.profile.ypar)
        dypar = ParameterProxy(self._dyname, self.profile.dypar)
        self.addParameter(xpar)
        self.addParameter(ypar)
        self.addParameter(dypar)

        # If we have a ProfileGenerator, set its Profile as well, and assign
        # the default residual equation if we're setting the Profile for the
        # first time.
        for gen in self._generators.values():
            gen.setProfile(profile)

        if self._eq is not None and seteq:
            self.setResidualEquation()

        return

    def addProfileGenerator(self, gen, name = None):
        """Add a ProfileGenerator to be used by this FitContribution.

        The ProfileGenerator is given a name so that it can be used as part of
        the profile equation (see setEquation). This can be different from the
        name of the ProfileGenerator used for attribute access.
        FitContributions should not share calculators instance. Different
        ProfileGenerators can share Parameters and ParameterSets, however.
        
        Calling addProfileGenerator sets the profile equation to call the
        calculator and if there is not a profile equation already.

        gen     --  A ProfileGenerator instance
        name    --  A name for the calculator. If name is None (default), then
                    the ProfileGenerator's name attribute will be used.

        Raises ValueError if the ProfileGenerator has no name.
        Raises ValueError if the ProfileGenerator has the same name as some
        other managed object.
        """
        if name is None:
            name = gen.name

        # Register the calculator with the equation factory
        self._eqfactory.registerGenerator(name, gen)
        self._addObject(gen, self._generators, True)

        # Set the default fitting equation if there is not one.
        if self._eq is None:
            self.setEquation(name)

        # If we have a Profile already, let the ProfileGenerator know about it.
        if self.profile is not None:
            calc.setProfile(self.profile)

        return

    def setEquation(self, eqstr, makepars = True, ns = {}):
        """Set the profile equation for the FitContribution.

        This sets the equation that will be used when generating the residual
        for this FitContribution.  The equation will be usable within
        setResidualEquation as "eq", and it takes no arguments.  Calling
        setEquation resets the residual equation.

        eqstr   --  A string representation of the equation. Any Parameter
                    registered by addParameter or setProfile, or function
                    registered by setCalculator, registerFunction or
                    registerStringFunction can be can be used in the equation
                    by name.
        makepars    --  A flag indicating whether missing Parameters can be
                    created by the Factory (default True). If False, then the a
                    ValueError will be raised if there are undefined arguments
                    in the eqstr. 
        ns      --  A dictionary of Parameters, indexed by name, that are used
                    in the eqstr, but not part of the FitRecipe (default {}).
        
        Raises ValueError if ns uses a name that is already used for a
        variable.
        Raises ValueError if makepars is false and eqstr depends on a Parameter
        that is not in ns or part of the FitContribution.

        """

        # Build the equation instance.
        eq = equationFromString(eqstr, self._eqfactory, buildargs = makepars)
        eq.name = "eq"
        # Register the equation
        self._registerEquation(eq.name, eq, check = False)
        # FIXME - this will have to be changed when proper swapping is
        # implemented.
        # Register any new Parameters.
        for par in self._eqfactory.newargs:
            self._addParameter(par)

        self._eq = eq
        self._eq.clicker.addSubject(self.clicker)

        if self.profile is not None:
            self.setResidualEquation()
        return

    def setResidualEquation(self, eqstr = None):
        """Set the residual equation for the FitContribution.

        eqstr   --  A string representation of the residual. If eqstr is None
                    (default), then the previous residual equation will be
                    used, or the chi2 residual will be used if that does not
                    exist.

        Two residuals are preset for convenience, "chiv" and "resv".
        chiv is defined such that dot(chiv, chiv) = chi^2.
        resv is defined such that dot(resv, resv) = Rw^2.
        You can call on these in your residual equation. Note that the quantity
        that will be optimized is the summed square of the residual equation.
        Keep that in mind when defining a new residual or using the built-in
        ones.

        Raises AttributeError if the Profile is not yet defined.
        Raises ValueError if eqstr depends on a Parameter that is not part of
        the FitContribution.

        """
        if self.profile is None:
            raise AttributeError("Assign the Profile first")


        chivstr = "(eq - %s)/%s" % (self._yname, self._dyname)
        resvstr = "(eq - %s)/sum(%s**2)**0.5" % (self._yname, self._yname)

        # Get the equation string if it is not defined
        if eqstr == "chiv":
            eqstr = chivstr
        elif eqstr == "resv":
            eqstr = resvstr
        elif eqstr is None:
            eqstr = self._reseqstr or chivstr

        self._reseqstr = eqstr

        self._reseq = equationFromString(eqstr, self._eqfactory)

        return

    def residual(self):
        """Calculate the residual for this fitcontribution.

        When this method is called, it is assumed that all parameters have been
        assigned their most current values by the FitRecipe. This will be the
        case when being called as part of a FitRecipe refinement.

        The residual is by default an array chiv:
        chiv = (eq() - self.profile.y) / self.profile.dy
        The value that is optimized is dot(chiv, chiv).

        The residual equation can be changed with the setResidualEquation
        method.
        
        """
        # Assign the calculated profile
        self.profile.ycalc = self._eq()
        # Note that equations only recompute when their inputs are modified, so
        # the following will not recompute the equation.
        return self._reseq()



# version
__id__ = "$Id$"

#
# End of file