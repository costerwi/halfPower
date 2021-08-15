"""Abaqus CAE plugin to estimate damping using the half power bandwidth method

Run doctest with command:
    abaqus python halfPower.py

Carl Osterwisch, August 2021
"""

import numpy as np
from abaqusConstants import NONE, FREQUENCY


def find_peaks(y):
    """Simple method to find indices of local maxima based on slope

    >>> find_peaks(np.sin(np.deg2rad(range(720))))
    array([ 90, 450])
    """

    yd = np.diff(y)
    i = np.logical_and(yd[1:]*yd[:-1] <= 0, yd[1:] <= yd[:-1])
    return 1 + np.nonzero(i)[0] # indices of local max


def interp_roots(x, y):
    """Interpolate to estimate all x where y=0

    >>> x = np.array(range(20))

    These roots are exactly at provided points:
    >>> interp_roots(x, (x - 10.)*(x - 12))
    array([ 10.,  12.])

    Linear interpolation does not give exact results for nonlinear function:
    >>> np.set_printoptions(precision=3)
    >>> interp_roots(x, (x - 8.5)*(x - 18.2))
    array([  8.526,  18.184])
    """

    x, y = np.asarray(x), np.asarray(y)
    i = np.nonzero(y[1:]*y[:-1] <= 0)[0] # indices where y crosses zero
    roots = []
    for x0, x1, y0, y1 in zip(x[i], x[i + 1], y[i], y[i + 1]):
        roots.append( x0 - y0/(y1 - y0)*(x1 - x0) ) # linear interpolation
    return np.unique(roots)


def find_damping(xy):
    """Estimate critical damping using half power method
    
    >>> x = range(720)
    >>> y = np.sin(np.deg2rad(x))
    >>> np.array(find_damping(np.array([x, y]).T))
    array([[  9.00000000e+01,   5.00000000e-01],
           [  4.50000000e+02,   1.00000000e-01]])
    """
    
    damping = []
    xy = np.asarray(xy)
    x = xy[:,0]
    for j in find_peaks(xy[:,1]):
        fn, amp = xy[j] # frequency and amplitude of peak
        y = xy[:,1] - amp/np.sqrt(2) # half power, approx -3 dB
        left = interp_roots(x[:j + 1], y[:j + 1])
        right = interp_roots(x[j:], y[j:])
        if len(left) and len(right):
            Q = fn/(right[0] - left[-1])
            damping.append([fn, 1/(2*Q)])
    return np.array(damping)


def plotDamping():
    """Called by Abaqus CAE to estimate critical damping in xyPlot
    """

    from abaqus import session, getWarningReply, CANCEL
    from visualization import QuantityType
    dampingType = QuantityType(type=NONE, label='Critical damping ratio')
    vp = session.viewports[session.currentViewportName]
    xyPlot = vp.displayedObject
    if not hasattr(xyPlot, 'charts'):
        return getWarningReply(
                'You must first display an XY Plot of frequency\nresponse in the current viewport',
                (CANCEL, )
                )
    chart = xyPlot.charts.values()[0]
    newCurves = []
    for curve in chart.curves.values():
        if FREQUENCY != curve.data.axis1QuantityType.type:
            continue # not vs frequency
        if NONE == curve.data.axis2QuantityType.type:
            continue # not a quantity
        data = curve.data.data
        damping = find_damping(data)
        if not len(damping):
            continue # no damping found

        n = 0 # find unique name
        while not n or session.xyDataObjects.has_key(name):
            n -= 1
            name = curve.data.name + ' DAMPING' + str(n)

        curve = session.Curve(
            xyData = session.XYData(
                name = name,
                legendLabel = curve.data.legendLabel + ' DAMPING',
                sourceDescription = 'Damping estimated from ' + curve.data.description,
                data = damping,
                axis1QuantityType = curve.data.axis1QuantityType,
                axis2QuantityType = dampingType,
                yValuesLabel = 'Critical Damping',
                )
            )
        curve.symbolStyle.setValues(
                show=True,
                size=2,
                )
        curve.lineStyle.setValues(show=False)
        newCurves.append(curve)
    chart.setValues(curvesToPlot=chart.curves.values() + newCurves)

if __name__ == '__main__':
    import doctest
    doctest.testmod()
