# Autogenerated with SMOP version 0.25... kinda... not really
# main.py scalecInterpPerturbations.m -o scalecInterpPerturbations.py
import numpy as np
def scalecInterpPerturbations(x,z,s,xi,lx,filtername,nmseitol,Ntotal,Ndone):
    """
     DOES NOT REMOVE A POLYNOMIAL TREND, AS TREND IS ASSUMED ALREADY REMOVED FROM
     PERTURBATION DATA, DEFAULTS TO ZERO VALUE IF NO DATA
    
     Input
       x, the nxm location of the data- repeated indices not handled well (ignored)
       z, the observations MINUS a TREND surface
       s, the the observation errors (i.e., standard deviations, rms, etc.)
          s is used to weight the observations as 1/s
          choose s=0 if no information is available about the weights
       xi, the interpolation locations
       lx, the interpolation weighting length scales
       filtername, the name of a filter to analyze:
          'quadloess'
          'linloess'
          'hanning'
          'boxcar'
       nmseitol, a maximum error level, if exceeded causes doubling of smoothing scales
           NOTE: if nmseitol=1 then this means we accept result with input scales
                 if nmseitol<1 then this means interpolation will successive doubling of scales to reach desired noise reduction
       Ntotal, the total number of interpolated points being processed (e.g., larger than N if doing tiles)
       Ndone, the total number of interpolated points already processed (e.g., number done in previous tiles)
       HWAITBAR, handle to waitbar
    
     Output
       zi, the estimate
       msei, the mean square interpolation error estimate (units of z)
       nmsei, the normalized mean square error
       msri, the mean square residuals
       HWAITBAR, the waitbar handle
    """
    # deal with input 
    N, m = np.shape(x)
    Ni, mi = np.shape(xi)
    
    if (Ntotal == None):#(nargin_() < 8 | (not Ntotal)):
        Ntotal = Ni
    if (Ndone == None):#(nargin_() < 9 | (not Ndone)):
        Ndone = 0
    
    # Fix up s, if constant
    if (np.size(s) == 1):
        s = np.tile(s, (N,1))
    
    # Deal with nans
    tmp = np.concatenate((x,z,s), axis=1)
    idd = (np.ravel(np.isfinite(np.sum(tmp, axis=1))).nonzero())[0]
    del tmp
    x = x[idd,:]
    z = z[idd]
    s = s[idd]
    if (np.shape(lx) == N and np.shape(lx) != Ni):
        # got to remove the corresponding scales 
        lx = lx[idd,:]
    
    N, m = np.shape(x)
    
    # Use weighted calculations on DATA
    wtol = 0.1 # tolerance for iterative convergence of weights
    s = s**2 # need variance, not standard deviation
    from supportingMethods import consistentWeight
    wt, var_z = consistentWeight(z, s, wtol)
    # normalize weights
    wt = (wt + np.spacing(1)) / (np.spacing(1) + max(wt))
    
    # eliminate useless variables
    tmp = np.array([])
    for i in xrange(0,m):
        tmp = np.append(tmp, np.std(x[:,i]))
    std_x = tmp
    del tmp
    idd = np.where(std_x == 0)[0]
    if (len(idd) > 0): # catch variables with zero variance (e.g., a profile)
        #for i in idd:
        std_x[idd] = 1
    
    # get the convolution kernel at adequate resolution
    Rmax = 1
    Dr = 0.01 # Need to descretize the continuous kernel function
    if (nmseitol == None): 
        nmseitol = np.inf # Never invoke tolerance 
        print 'scalecInterpPerturbations: Setting maximum nmse tolerance to ', nmseitol
    if 'quadloess' == filtername:
        # MUST DO THIS CORRECTLY FOR N-D
        from supportingMethods import loess_kernelND
        ri, ai = loess_kernelND(m, 2)
        Fc = 0.7 # Here is the half-power point
    elif 'linloess' == filtername:
        from supportingMethods import loess_kernelND
        ri, ai = loess_kernelND(m, 1)
        Fc = 0.4 # Here is the half-power point
    elif 'hanning' == filtername:
        from supportingMethods import hanning_wt
        ri = np.arange(0, (Rmax+Dr), Dr)
        ai = hanning_wt(ri)
        Fc = 0.4
    elif 'boxcar' == filtername:
        ri = np.arange(0, (Rmax+Dr), Dr)
        ai = np.ones((len(ri), 1), float)
        Fc = 0.25
    elif 'si' == filtername:
        ri = np.arange(0, (Rmax+Dr), Dr)
        ai = np.ones((len(ri), 1), float)
        Fc = 1
    else:
        print 'Filter window, ', filtername,' not found'
    # Change the shape of ri and ai for compatibility 
#    ri = np.reshape(ri, (len(ri),)) # go from shape (len(ri),1) to (len(ri),)... if of that shape
#    ai = np.reshape(ai, (len(ai),)) # go from shape (len(ai),1) to (len(ai),)... if of that shape
    #ri = ri[:,np.newaxis]
    # initialize output
    zi = np.zeros((Ni,1), float)
    nmsei = np.ones((Ni,1), float)
    msei = np.ones((Ni,1), float)
    msri = np.ones((Ni,1), float)
    
    for i in xrange(0, Ni):
        # center on point of interest
        y = x - (np.ones((N,1), float) * xi[i,:])
        
        # now scale if using individual smoothing scales         
        if (len(lx) == m):
            # constant scale obs. and interp. locations
            y = np.dot(y, np.diag(1.0 / lx))
        elif (len(lx) == N):
            # scale the data
            y = y / lx
        elif (len(lx) == Ni):
            y = np.dot(y, np.diag(1.0 / lx[i,:]))
        else:
            print 'smoothing scales not interpreted: ', N, Ni, np.size(lx)
        
        # Convert input to radial 
        r = np.sqrt(np.sum(y**2, axis=1))
        
        # expand smoothing scales until tolerance met
        cnt = 0
        while ((nmsei[i] > nmseitol and cnt < 10) or cnt == 0): # do it once, at least
            p = 2**cnt
            
            # allow for computationally intensive methods here
            cnt += 1
            if 'si' == filtername:
                # there is not an abrupt cutoff with si, so feed it more data
                aid = np.nonzero(r < (8 * p))
                na = len(aid)
                a = np.zeros((na,1),float) # default to first guess (also called norm)
                # got to compute full thing
                from supportingMethods import si_wt
                a = si_wt(y[aid], wt[aid]) # note, wt is %var that is signal
            else:
                aid = np.nonzero(r < p)[0]
                na = len(aid)
                a = np.zeros((na,1), float) # default to first guess (also called norm)
                from scipy import interpolate
                f = interpolate.interp1d(ri,ai.flatten(1))
                a = f(r[aid]/p)
               # from scipy.interpolate import interp1d
               # interpObj = interp1d(ri, ai, kind = 'linear')
               # a = interpObj.__call__(r[aid] / p)
                # apply a priori weights
                if (np.size(a) == 1):
                    a = a[0]
                elif(np.size(a) == 0):
                    a = 0
                if (np.size(aid) != 0):
                    a = a * wt[aid[0]][0] # some wierd stuff happens with the indices... just go with it
            
                suma = np.sum(a)
                if (abs(suma) > 0):
                    a = a / suma
                   
            # check weights
            if (np.sum(a) > 0):
                # compute error, noise passed, fraction of target variance not explained
                #            (noise)  +  (    lost signal    )
                nmsei[i] = np.dot(a.conj().T, a) * (1 - np.spacing(1)) # want to distinguiush points with at least one nonzero weight
                # actual error is the noise passed (nmsei*s) + signal reduced (1-nmsei)*s
            else:
                # weights all zero                 
                nmsei[i]=1
                
        # account for deviation from target scales with fraction of wavenumber band used
        q = p ** (- m)
        nmsei[i] = (1 - q * (1 - nmsei[i]))
        
        # convolve against data
        a_ConjugateTranspose = np.reshape(a.conj().T, (1, len(a.conj().T)))
        tmp = z[aid]
        zi[i] = np.dot(a_ConjugateTranspose, z[aid])
        
        if (nmsei[i] < 1 and na > 0):
            # and weighted residuals are
            tmp = np.reshape(a, (len(a), 1))
            y = (z[aid] - zi[i]) * tmp
            del tmp
            msri[i] = np.dot(y.conj().T, y) / nmsei[i][0]
            msri[i] = ((na - 1) * msri[i] + np.dot(a_ConjugateTranspose, s[aid])[0,0]) / na
            # weighted mean square residual 
            msei[i] = msri[i] * nmsei[i] / (1 - nmsei[i]) # predicted mean square error
        else:
            # set it to one
            nmsei[i] = 1
    
    return zi, msei, nmsei, msri

def scalecInterp(x, z, s, xi, lx, filtername, nmseitol):
    """
    Created on Wed Jul 23 14:32:36 2014
    [zi, msei, nmsei, msri] = scalecInterp(x, z, s, xi, lx, filtername, nmseitol, WB);
     
     This is a stand-alone general purpose interpolator. 
     It remvoes a linear (or planar) trend first and then calls scalecInterpPerturbations 
    
     Input
       x, the nxm location of the data- repeated indices not handled well (ignored)
       z, the observations
       s, the the observation errors (i.e., standard deviations, rms, etc.)
          s is used to weight the observations as 1/s
          choose s=0 if no information is available about the weights 
       xi, the interpolation locations
       lx, the interpolation weighting length scales
       filtername, the name of a filter to analyze:
          'quadloess'
          'linloess'
          'hanning'
          'boxcar'
       nmseitol, a maximum error level, if exceeded causes doubling of smoothing scales
           NOTE: if nmseitol=1 then this means we accept result with input scales
                 if nmseitol<1 then this means interpolation will successive doubling of scales to reach desired noise reduction
       WB, a flag to use the waitbar to show progress. WB=1 will show waitbar, missing,empty, or other value won't
     
     Output
       zi, the estimate
       msei, the mean square interpolation error estimate (units of z)
       nmsei, the normalized mean square error
       msri, the mean square residuals
    """
    # fix up input data
    Ni, mi = np.shape(xi)
    N, m = np.shape(x)
    
    # deal with nans
    if(np.size(s) == 1):
        s = np.tile(s, (N,1)) 
    
    tmp = np.concatenate((x,z,s),axis=1)
    idd = np.nonzero(np.isfinite(np.sum(tmp, axis=1)))
    x = x[idd,:]
    x = x[0] # some dimensional wierdness happens with the above line of code...
    z = z[idd]
    s = s[idd]
    
    if(np.size(lx) == N and np.size(lx) != Ni):
        # got to remove the corresponding scales
        lx = lx[idd,:]
    N, m = np.shape(x)
    
    # need to remove trend once, # first, shift and scale grid and data
    mean_xi = np.mean(xi, axis=0) # center on output center
    x = x - np.tile(mean_xi, (N,1))
    xi = xi - np.tile(mean_xi, (Ni,1))
    tmp = np.array([])
    for i in xrange(0,m):
        tmp = np.append(tmp, np.std(x[:,i]))
    std_x = tmp
    del tmp
    idd = np.nonzero(std_x == 0)
    if(np.size(idd) > 0): # catch variables with zero variance (e.g., a profile)
        std_x[idd] = 1
    
    L = np.diag(1 / std_x)
    x = np.dot(x, L)
    xi = np.dot(xi, L)
    lx = np.dot(lx, L)
    
    # need some consistent weights
    wtol = 0.01
    from supportingMethods import consistentWeight
    wt, var_z = consistentWeight(z, s**2, wtol)
    
    # do regression to remove a norm field
    btrend = np.zeros((mi+1,1), float)
    bi = btrend
    # only compute against variables with variance
    varid = np.nonzero(std_x > 0)
    if(np.size(varid) > 0):
        # this is just for getting the data ready, so it is meant to be bullet proof, not statistically pure!
        tmp1 = np.reshape(x[:,varid], (N,m))
        tmp2 = np.concatenate((np.ones((N,1), float), tmp1), axis=1)        
        from supportingMethods import regr_xzw
        (btrend[0], btrend[varid[0][0]+1], btrend[varid[0][1]+1]), (bi[0], bi[varid[0][0]+1], bi[varid[0][1]+1]) = regr_xzw(tmp2, z, wt)
        print 'removed order ', 1 ,' polynomial \n'
        del tmp1, tmp2
    
    # regression failed if nan
    btrendHasNan = False
    for i in btrend:
        if np.isnan(i):
            btrendHasNan = True
    if(btrendHasNan == True):
        # pad with zero
        btrend = np.zeros((len(btrend), 1), float)
    
    tmp = np.concatenate((np.ones((N,1), float), x), axis=1)
    ztrend = np.dot(tmp, btrend)
    del tmp    
    
    # compute deviations from trend
    z = z - ztrend
    
    # pass the trend-removed data to scalecInterpPerturbations
    from scalecInterpolation import scalecInterpPerturbations
    zi, msei, nmsei, msri = scalecInterpPerturbations(x, z, s, xi, lx, filtername, nmseitol, Ntotal=Ni, Ndone=0)
    
    # compute trend on data locations
    tmp = np.concatenate((np.ones((Ni,1), float), xi), axis=1)
    ztrend = np.dot(tmp, btrend)
    del tmp
    
    # replace trend
    zi = zi + ztrend
    
    return zi, msei, nmsei, msri

def scalecInterpTilePerturbations(x, z, s, xi, lx, filtername, nmseitol):
    """
     [Zi, Msei, Nmsei, Msri] = scalecInterpTilePerturbations(x, z, s, xi, lx, filtername, nmseitol, WB);
    
     optimize interpolation for regular grid output by breaking into bite-sized tiles
     which are passed to scalecInterpPerturbations (which does not remove any trend)
    
     Input
       x, the nxm location of the data- repeated indices not handled well (ignored)
       z, the observations
       s, the the observation errors (i.e., standard deviations, rms, etc.)
          s is used to weight the observations as 1/s
          choose s=0 if no information is available about the weights
       xi, the interpolation locations
       lx, the interpolation weighting length scales
       filtername, the name of a filter to analyze:
          'quadloess'
          'linloess'
          'hanning'
          'boxcar'
       nmseitol, a maximum error level, if exceeded causes doubling of smoothing scales
           NOTE: if nmseitol=1 then this means we accept result with input scales
                 if nmseitol<1 then this means interpolation will successive doubling of scales to reach desired noise reduction
       WB, a flag to use the waitbar to show progress. WB=1 will show waitbar, missing,empty, or other value won't
    
     Output
       zi, the estimate
       msei, the mean square interpolation error estimate (units of z)
       nmsei, the normalized mean square error
       msri, the mean square residuals
    
     change log
     12 Feb 2009, NGP,  disabled the figure display so large regions don't croak
    """

    # check dimensions
    Ni, mi = np.shape(xi)
    
    if(nmseitol == None): #set None as default input 
        #nmseitol = inf # never invoke tolerance
        nmseitol = 1 / (mi**2) # default tol ensures some data used
        print 'scalecInterpTile: setting maximum nmsei tolerance to ', nmseitol,'\n'
    
    # detect gridded data
    idxi = np.nonzero(xi[:,0] == xi[0,0])
    idyi = np.where(xi[:,1] == xi[0,1])
    
    # if second occurrance of x(1) coincides with end of occurrances of y(1), suspect gridded data
    try:
        if(idyi[0][1] - 1 == idxi[0][-1]):
            print 'gridded output suspected \n'
    except:
        # no evidence for grid, must interpolate all at once
        # send to stand-alone interp
        print 'output not a 2-d grid \n'
        from scalecInterpolation import scalecInterp
        Zi, Msei, Nmsei, Msri = scalecInterp(x, z, s, xi, lx, filtername, nmseitol)
        return Zi, Msei, Nmsei, Msri
    
    nyi = idxi[0][-1] + 1
    nxi = Ni / nyi  
    
    # modify to handle time input for single time output on 2-d-h grid
    tmp = np.reshape(np.fix(nxi), (1)) # np.fix returns a 0-d array, so it must be reshaped to a 1-d array
    if (nxi != tmp[0]):
        print 'indices not consistent with gridded output, continuing to interp \n'
        # send to stand-alone interp
        from scalecInterpolation import scalecInterp
        Zi, Msei, Nmsei, Msri = scalecInterp(x, z, s, xi, lx, filtername, nmseitol)
        return Zi, Msei, Nmsei, Msri
    else:
        # we still think we have gridded data
        Xi = np.reshape(xi[:,0], (nxi,nyi)).T
        Yi = np.reshape(xi[:,1], (nxi,nyi)).T
        # and we are requesting single time
    
        if (mi == 3 and all(xi[:,2] == xi[0,2])):
            Ti = xi[0,2]
        xitest = Xi[0,:] 
        yitest = Yi[:,0]  
        Xitest, Yitest = np.meshgrid(xitest, yitest)
        # check carefully and pass to scalecInterp if fail
        if (not np.all(Xi == Xitest) and np.all(Yi == Yitest)):
            print 'inidices not consistent with gridded output, continuing to interp \n'
            # send to stand-alone interp
            from scalecInterpolation import scalecInterp
            Zi, Msei, Nmsei, Msri = scalecInterp(x, z, s, xi, lx, filtername, nmseitol)
            return Zi, Msei, Nmsei, Msri
    del tmp
    # if we survived to here, we have gridded output
    # xi and yi are now row,col vectors of grid indices
    xi = np.reshape(xitest, (1,len(xitest)))
    yi = np.reshape(yitest, (len(yitest),1))
    del xitest, yitest, Xitest, Yitest
    
    # fix up input data
    N, m = np.shape(x)
    
    # deal with nans
    tmp1 = np.concatenate((x,z,s), axis=1)
    idd = np.nonzero(np.isfinite(np.sum(tmp1, axis=1)))
    x = x[idd[0],:]
    z = z[idd]
    s = s[idd]
    if (np.size(lx) == N and np.size(lx) != Ni):
        # got to remove the corresponding scales
        if(all(np.shape(lx) == np.shape(x))): # May not need term 'all'
            print 'smoothing scales vary with data'
            lx = lx[idd]
    N, m = np.shape(x)
    
    # need to remove trend once,
    # first, shift and scale grid and data
    # shift, center on output center
    mean_xi = np.mean(xi)
    mean_yi = np.mean(yi)
    xi = xi - mean_xi
    yi = yi - mean_yi
    Xi = Xi - mean_xi
    Yi = Yi - mean_yi
    x[:,0] = x[:,0] - np.repeat(mean_xi,N)
    x[:,1] = x[:,1] - np.repeat(mean_yi,N)
    
    # scale
    tmp = np.array([])
    for i in xrange(0,m):
        tmp = np.append(tmp, np.std(x[:,i]))
    std_x = tmp
    del tmp
    idd = np.nonzero(std_x == 0)
    if(np.size(idd) > 0): # catch variables with zero variance (e.g., a profile)
        std_x[idd] = 1 
    L = np.diag(1 / std_x) 
    x = np.dot(x, L)
    xi = xi * L[0,0]
    yi = yi * L[1,1]
    Xi = Xi * L[0,0]
    Yi = Yi * L[1,1]
    
    lx = np.dot(lx, L) # Matrix multiplication, not element-wise multiplication
    # add time
    if (mi == 3):
        Ti = Ti * L[2,2] 
    
    # need some consistent weights
    wtol = 0.01
    try:
        from supportingMethods import consistentWeight
        wt, var_z = consistentWeight(z, s**2, wtol)
    except:
        print 'setting var_z = s^2'
        # if this dies, var_z = s.^2 is a nice guess
        var_z = s**2
    
    # sort out the lx input
    if (np.size(lx[:]) == mi):
        # same everywhere
        lxflag = 'constant'
    elif(np.size(lx[:,1], axis=0) == Ni):
        lxflag = 'ongrid'
        lxgrid = np.reshape(lx[:,0], (nyi,nxi))
        lygrid = np.reshape(lx[:,1], (nyi,nxi))
        if(mi == 3):
            ltgrid = np.reshape(lx[:,2], (nyi,nxi));
    else:
        # assume on data
        lxflag = 'ondata'
    
    # get optimal tile
    # first compute smoothness/domain size ratio
    lk = np.max(np.array([np.min(lx[:,0]), np.min(lx[:,1])]) / np.array([np.max(xi)-np.min(xi), np.max(yi)-np.min(yi)]))
    if(np.isnan(lk) or np.isinf(lk)):
        lk = 0
    # next, the optimal number of tiles
    kopt = np.sqrt(nxi * nyi * (1+lk))
    ropt = (1/kopt) + kopt / ((1+lk) * nxi * nyi)
    # number of tiles in x,y dims
    kx = np.ceil(np.sqrt(kopt)) # proportion to grid dimensions
    ky = np.ceil(kopt / kx)
    kopt = kx * ky 
    ropt = (1 / kopt) + kopt / ((1+lk) * nxi * nyi)

    # divide grid points per tile, roughly
    if(kx == 1):
        nkx = nxi
    else:
        nkx = float(int(nxi / kx)) # must round down # NOTE: float(int()) is a fix for numpy.fix returning a 0-d array that can't be indexed... matlab fix doesn't do that...
        if(nkx < 1):
            nkx = 1
            kx = nxi # make sure we do them all
    
    if(ky == 1):
        nky = nyi
    else:
        nky = float(int(nyi / ky))
        if(nky < 1):
            nky = 1
            ky = nyi
    print 'number of tiles = ', kopt ,', expected efficiency = ', ropt ,', xi/tile = ', nkx ,', yi/tile = ', nky ,' \n'
    
    # specify overlap
    Lmax = 10 * np.array([max(lx[:,0]), max(lx[:,1])])
    
    # init output
    Zi = np.nan * np.ones((nyi,nxi), float)
    Nmsei = np.ones((nyi,nxi), float)
    Msei = np.nan * np.ones((nyi,nxi), float)
    Msri = np.nan * np.ones((nyi,nxi), float)
    
    # begin
    Ndone = 0
    for i in xrange(0, int(kx)):
        idxi = np.arange(0, int(nkx)) + i * int(nkx) # indices to interp this time
        if(i == kx-1 and  idxi[-1] != nxi):
            idxi = np.arange(idxi[0], nxi) # catch the end here
        # what is appropriate overlap?
        xmin = xi[0,idxi[0]] - Lmax[0] # find tile limits
        xmax = xi[0,idxi[-1]] + Lmax[0]
        idx = np.where((x[:,0] > xmin) & (x[:,0] < xmax))[0] # get the useful data
        if(len(idxi) > 0):
            # repeat at each yi
            for j in xrange(0, int(ky)):
                idyi = np.arange(0, int(nky)) + (j+1) * int(nky) # indices to interp this time
                if(j == ky-1 and idyi[-1] != nyi):
                    idyi = np.arange(idyi[0], nyi) # catch the end here
                ymin = yi[idyi[0],0] - Lmax[1]
                ymax = yi[idyi[-1],0] + Lmax[1]
                idxy = idx[np.where((x[idx,1] < ymax) & (x[idx,1] > ymin))[0]]
                if(np.size(idxy) > mi):
                    # send to interpolator
                    tmp1, tmp2 = np.meshgrid(idyi, idxi)
                    Xii = Xi[tmp1,tmp2].T
                    Yii = Yi[tmp1,tmp2].T
                    # deal with smoothing scales
                    if (lxflag == 'constant'):
                        L = lx
                    elif (lxflag == 'ongrid'):
                        lxii = lxgrid[tmp1,tmp2].T
                        lyii = lygrid[tmp1,tmp2].T
                        L = np.array([lxii.flatten(), lyii.flatten(1)]).T
                        if(mi == 3):
                            ltii = ltgrid[tmp1,tmp2].T
                            ltii = np.reshape(ltii, (np.size(ltii),1))
                            L = np.concatenate((L, ltii), axis=1)
                    elif(lxflag == 'ondata'):
                        L = lx[idxy]
                    # now, send to interp
                    if(mi == 2):
                        # interp 2-d
                        from scalecInterpolation import scalecInterpPerturbations
                        zi, msei, nmsei, msri = scalecInterpPerturbations(x[idxy,:], z[idxy], s[idxy], np.array([Xii.flatten(1), Yii.flatten(1)]).T, L, filtername, nmseitol, Ni, Ndone)
                    elif(mi == 3):
                        # interp 2-d + time
                        from scalecInterpolation import scalecInterpPerturbations
                        zi, msei, nmsei, msri = scalecInterpPerturbations(x[idxy,:], z[idxy], s[idxy], np.array([Xii.flatten(1), Yii.flatten(1), Ti+0*Xii.flatten(1)]).T, L, filtername, nmseitol, Ni, Ndone)
                    zi = np.reshape(zi, (len(idxi), len(idyi))).T
                    msei = np.reshape(msei, (len(idxi), len(idyi))).T
                    nmsei = np.reshape(nmsei, (len(idxi), len(idyi))).T
                    msri = np.reshape(msri, (len(idxi), len(idyi))).T
                    Zi[idyi[0]:idyi[-1]+1, idxi[0]:idxi[-1]+1] = zi
                    Msei[idyi[0]:idyi[-1]+1, idxi[0]:idxi[-1]+1] = msei
                    Nmsei[idyi[0]:idyi[-1]+1, idxi[0]:idxi[-1]+1] = nmsei
                    Msri[idyi[0]:idyi[-1]+1, idxi[0]:idxi[-1]+1] = msri
                    Ndone = Ndone + len(idyi) * len(idxi)
                    del tmp1, tmp2
                    #if(etime(clock,tcheck)>60)
                #    tcheck = clock
                #    print 'progres: completed', Ndone ,' of ', nyi*nxi ,' points \n' 
    #tend = clock# FIND PYTHON EQUIVALENT
    #print 'interpolated ', np.fix(nyi*nxi/(etime(tend,tstart))) ,' points per second (tiled) \n'
                    
    # return output in cols
    Zi    = Zi.flatten(1)
    Msei  = Msei.flatten(1)
    Nmsei = Nmsei.flatten(1)
    Msri  = Msri.flatten(1)
    
    # fix up error too
    # The following probably can be done more effectively
    idd = []
    index = 0
    for i in Msei:
        if(np.isnan(i)):
            idd.append(index)
        index += 1
    idd = np.array(idd)
    if (np.size(idd) > 0):
        Msei[idd] = var_z + np.mean(s**2)
        Msri[idd] = Msri[idd]
    
    return Zi, Msei, Nmsei, Msri 
    
def scalecInterpTile(x, z, s, xi, lx, filtername, nmseitol):
    """
     [ZI, MSEI, NMSEI, MSRI] = scalecInterpTile(x, z, s, xi, lx, filtername, nmseitol,WB);
    
     remove a plane-trend and pass to scalecInterpTilePerturbations (which does not remove any trend)
     
     Input
       x, the nxm location of the data- repeated indices not handled well (ignored)
       z, the observations
       s, the the observation errors (i.e., standard deviations, rms, etc.)
          s is used to weight the observations as 1/s
          choose s=0 if no information is available about the weights 
       xi, the interpolation locations
       lx, the interpolation weighting length scales
       filtername, the name of a filter to analyze:
          'quadloess'
          'linloess'
          'hanning'
          'boxcar'
       nmseitol, a maximum error level, if exceeded causes doubling of smoothing scales
           NOTE: if nmseitol=1 then this means we accept result with input scales
                 if nmseitol<1 then this means interpolation will successive doubling of scales to reach desired noise reduction
       WB, a flag to use the waitbar to show progress. WB=1 will show waitbar, missing,empty, or other value won't
     
     Output
       zi, the estimate
       msei, the mean square interpolation error estimate (units of z)
       nmsei, the normalized mean square error
       msri, the mean square residuals
    
     modifications by updating the trend only where valid perturbations were interpolated
    """
    # catch  input
    Ni, mi = np.shape(xi)
    N, m = np.shape(x)
        
    # need some consistent weights
    wtol = 0.01
    from supportingMethods import consistentWeight
    wt, var_z = consistentWeight(z, s**2, wtol)
    
    # do regression to remove a norm field
    btrend = np.zeros((mi+1,1),float)
    bi = btrend
    
    # only compute against variables with variance
    tmp = np.array([])
    for i in xrange(0,m):
        tmp = np.append(tmp, np.std(x[:,i]))
    std_x = tmp
    del tmp
    idd = np.nonzero(std_x == 0)
    if (np.size(idd) > 0): # catch variables with zero variance (e.g., a profile)
        std_x[idd] = 1
    
    varid = np.nonzero(std_x > 0)
    if(np.size(varid) > 0):
        # this is just for getting the data ready, so it is meant to be bullet proof, not statistically pure!
        tmp1 = np.reshape(x[:,varid], (N,m))
        tmp2 = np.concatenate((np.ones((N,1), float), tmp1), axis=1)        
        from supportingMethods import regr_xzw
        (btrend[0], btrend[varid[0][0]+1], btrend[varid[0][1]+1]), (bi[0], bi[varid[0][0]+1], bi[varid[0][1]+1]) = regr_xzw(tmp2, z, wt)
        print 'removed order ', 1 ,' polynomial \n'
        del tmp1, tmp2
       
    # regression failed if nan
    for i in btrend:
        if(np.isnan(i)):
            btrendHasNan = True
    if (btrendHasNan):
        # pad with zero
        btrend = np.zeros((len(btrend),1), float)
     
    # remove trend
    tmp = np.concatenate((np.ones((N,1), float), x), axis=1)
    if (np.size(btrend, axis=0) != np.size(tmp,axis=1)): # check to see if the axes of btrend and tmp are compatible for matrix multiplication
        nbt, mbt = np.shape(btrend) # if they aren't, identify the axes of btrend
        diffAxis = np.size(tmp,axis=0) - np.size(btrend, axis=0) # obtain the difference between the two incompatible axes
        diffArray = np.zeros((diffAxis, mbt)) # make an array to be used as padding for btrend that is of length of the differnce of the incompatible axes
        btrend = np.append(btrend, diffArray)#, axis=1) # append the padding array 
        btrend = np.reshape(btrend, (np.size(btrend, axis=0),1))
        #btrend = np.reshape(btrend, (1, np.size(btrend,axis=0))) # flip the indices of btrend for matrix multiplication 
    ztrend = np.dot(tmp, btrend) # finally... multiply the matrices
    z = z - ztrend 
    
    # send to interp tile perturbations
    from scalecInterpolation import scalecInterpTilePerturbations
    Zi, Msei, Nmsei, Msri = scalecInterpTilePerturbations(x, z, s, xi, lx, filtername='hanning', nmseitol=nmseitol)#, WB)
    
    # replace the trend - except where useless
    tmp = np.concatenate((np.ones((Ni,1), float), xi), axis=1)
    ztrend = np.dot(tmp, btrend)
    ztrend = np.reshape(ztrend, np.size(Zi))
    idgood = np.where(Nmsei != 1) and np.where(Nmsei != 0)
    Zi = Zi.flatten(1)
    Zi[idgood] = Zi[idgood] + ztrend[idgood]      
    
    return Zi, Msei, Nmsei, Msri
