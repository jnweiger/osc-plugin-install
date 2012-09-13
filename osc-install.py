#
# Rewrite of the builtin install cludge...
#
# (C) 2010-2012, jw@suse.de, Novell Inc., openSUSE.org
# Distribute under GPLv2 or GPLv3
#
# 2010-10-12, jw V0.1 -- initial draft
# 2011-03-23, jw V0.2 -- added --force to allow downgrades. Finished platform matching. 
#                        Uses getpac_default_project, rather than enabled zypper repos.
# 2011-03-24, jw V0.3 -- type 'a' to add repo permanently.
# 2011-03-29, jw V0.4 -- know the ibs repo url default.
# 2011-03-31, jw V0.5 -- osc bse integrated.
#                        zypper --gpg-auto-import-keys helps reducing the number of questions asked.
# 2011-04-11, jw V0.6 -- using osc_cache, added -I option.
# 2011-05-03, jw V0.7 -- guessing perl package names
# 2011-05-14, jw V0.8 -- options -v and --arch added. arch matching added. debugging for sled and x86_64
# 2011-05-14, jw V0.9 -- crude sorting of choices: if project matches platform, put this first.
# 2011-05-20, jw V0.10 -- bugfix proj_name.
# 2011-05-30, jw V0.11 -- bugfix system_name_words
# 2012-01-20, jw V0.12 -- added hardcoded urls for 12.1/repo/oss, non-oss; for completeness only.
#                         uploaded to https://gitorious.org/osc-plugin-install/
# 2012-01-22, jw V0.13 -- class TeePopen added. 
#                         trying unpublished packages as a fallback, code half done.
# 2012-01-23, jw V0.14 -- using get_binarylist() and get_binary_file(), finishing fallback code.
#                         Improved _user_prompt() .. msg is not None ..., packman download url added.
# 2012-02-21, jw V0.15 -- improved _matches_in_name() to prefer exact matches over suffix matches.
# 2012-07-12, jw V0.16 -- no stacktrace, when package does not exist.
# 2012-09-13, jw V0.17 -- also weed out .xml files! -U --prefer-unpublished added
#
# FIXME: osc ll -b KDE:Distro:Factory digikam
#        shows packages for 12.2, osc in does not.
#
# osc in [project] package
# is a user interface for zypper in [-p project_repo_url ] package; osc thus
# becomes the swiss-army knive of packaging. 
# osc mkpac; wget; vi; osc build; osc commit; osc install; done.
#
# The most striking difference is, that osc install can find the correct
# repository url by itself in most cases. It allows users to think in terms of
# projects and packages, and just forget about repository URLs.
#
# If you want to specify a particular project, you can do so by project name.
# otherwise osc in will honor the repository list you compiled when you used
# zypper. But unlike zypper, it does not simply fail when a package (or
# dependency) cannot be found through these zypper repositories, it continues
# to search the build service and suggests projects that might have what you
# need. 
#
# Osc install prompts you with candidate packages from a list of projects that
# build the package for your system. It can discern platform and architecture
# from /etc/SuSE-release and/or your ~/.oscrc build_project setting.
#
# Osc install suggests to add repo URLs for newly used projects to the zypper 
# repository list. This has little importance for osc, but is very
# helpful, when you have to directly use zypper again some day.
# 
# "osc in" actually just calls "zypper -p --from" most of the time to 
# get the dependencies resolved correctly and such.
#
# The second benefit is with project layering.
# Packages from a project that is using complex repository paths (aka layering)
# can be installed easily from the web-UI, where yast receives 
# a helping ymp file. 
# With zypper, packages from such a project just fail due to missing dependendcies.
#
# (or worse, zypper may 'succeed' in resolving dependencies from different
# repositories).
# 'osc in' analyzes the meta data of the project, and creates the proper list
# of repositories for zypper, just as yast would do.
# Project owners often pull in all the dependencies of their packages
# into their projects, (via link or aggregate), just to avoid this problem.
#  That should never be needed.
#
# As third benefit is it saves bandwidth.
# 'osc in' cooperates with 'osc build'. Whenever it downloads a package for
# installation, you can also add it to the package cache. This saves duplicate
# downloads during package development.  And vice versa of course: When you do
# 'osc build; osc in' you have good chances, that nothing needs to be
# downloaded during 'osc in' -- because it looks (unlike zypper) into your
# package caches. Zypper has a per-repository property 'keeppackages' 
# which would cache them in /var/cache/zypp/packages -- this is helpful.
#
# 'osc in' needs no parameters, if called within a package checkout directory.
# It will install what 'osc ls -b' would list for that package directory.
# Except -debuginfo and -devel packages, which are not installed by default
#  (but printed out, so that you know.)
#
# This plugin can also be called as '/usr/bin/apt-get'.
# In this case, its options very closely resembles the original 
# apt-get. That could pacify some ex-debian users, who would possibly
# freak out, when they learn the raw complexity of zypper.
#
# One of the hardest task is to hide most 
#  repository/platfrom/project/distribution details from the user. 
# End users and normal packagers should not need to learn the 
# difference between openSUSE_11.3 and openSUSE:11.3 -- they should be allowed
# to use either spelling in all cases.
# We do that, by initially analyzing disturls found in your rpm database
# A typical disturl reads:
# obs://build.opensuse.org/Documentation:Tools/openSUSE_11.3/ccedd5c76ce44fd2d48348fd9249072a-sikuli
# where 'Documentation:Tools' is a project, and 'openSUSE_11.3' is a platform.
# Zypper would have a corresponding repository
# http://download.opensuse.org/repositories/Documentation:/Tools/openSUSE_11.3
# (Note the hideous '/' character between 'Documentation:' and 'Tools'!)

# Another example:
# obs://build.opensuse.org/openSUSE:11.3:Update:Test/standard/07bb29ae70e34affb224de39e2fab3ba-java-1_6_0-sun
# The corresponding build service repo is known by osc ls -b is:
# https://api.opensuse.org/build/openSUSE:11.3:Update:Test/standard/i586/java-1_6_0-sun
# because it has no location on the mirrors, it is cached as
# /var/tmp/osbuild-packagecache/openSUSE/var/tmp/osbuild-packagecache/openSUSE\:11.3\:Update\:Test/standard/i586/
# its use would circumvent the 'published' flag, and put load on the api, that
# should be on the mirrors.
# its corresponding zypper repository is
# http://download.opensuse.org/update/11.3/
#  -> it appears there is no public mapping between download.opensuse.org directories and 
#     projects.
#  -> We could crawl the entire download.opensuse.org,
#     pull a few rpms from each directory and thus learn which projects 
#     are behind.
#  -> this is a TODO for a centralized mapping service, which this plugin could query.
#
# http://download.opensuse.org/repositories/openSUSE:/11.3:/NonFree/standard
# 
# FIXME: 
# If your package requires a virtual provide, current zypper repo metadata is needed to 
# map this to package names.  E.g.
# Two ways how this can fail:
# a) the package was recently added to a different repo, which is not refreshed
#    when running osc in. (osc in refreshes only the one repo, from which the 
#    package comes)
# b) the repo where those dependendcies should come from are not in the zypper list 
#    at all. osc in suggests to add repos, but one may not want to do that often.
# E.g:
# Problem: nothing provides libfreeimageplus.so.3()(64bit) needed by freecad-devel-0.13rc.svn5443-32.1.x86_64
# If you see this, run 'sudo zypper ref' then retry. If it works it was issue a).
# If not, see if the repo list printed by zypper ref, contains all needed repos.
# Solution: parse the project layering, add all repos, that are needed, then run the 
# install.
# FIXME: osc in should print out the description from meta pkg, so that the user 
# has something meaningful to read. Packagers may also put special hints there about the 
# usage or installation of the package.


import traceback
global OSC_INS_PLUGIN_VERSION, OSC_INS_PLUGIN_NAME
OSC_INS_PLUGIN_VERSION = '0.17'
OSC_INS_PLUGIN_NAME = traceback.extract_stack()[-1][0] + ' V' + OSC_INS_PLUGIN_VERSION

@cmdln.hide(1)
@cmdln.alias('in')
@cmdln.option('-p', '--platform', metavar='SUSE_RELEASE', help='platform substring to match. Default: guess platform from /etc/SuSE-Release')
@cmdln.option('-a', '--arch', metavar='ARCH', help='system architecture. Default: guess platform from /etc/SuSE-Release')
@cmdln.option('-f', '--first', action='store_true', help='if multiple projects offer a package, choose the first. Default: Ask user')
@cmdln.option('-v', '--verbose', action='store_true', help='babble while working')
@cmdln.option('-I', '--no-cache', action='store_true', help='ignore cached packages, always download. Default: check build cache /var/tmp/osbuild-packagecache')
@cmdln.option('-U', '--prefer-unpublished', action='store_true', help='Grab unpublished binary directly from the API. Usefull if publishing is slow. Default: use normal mirror system.')
#@cmdln.prep(cwd_proj_pack)
def do_install(self, subcmd, opts, *args):
    """${cmd_name}: install a package after build via zypper in -r

    CAUTION: Experimental code. This needs a sane 
    algorithm to derive a repourl from (apiurl,project,package)

    osc in 
        take PROJECT name and PACKAGE name from current directory.

    osc in PACKAGE
        find PACKAGE in this build service. The project of the current directoy, (if any) 
        has highest precedence, followed by the projects listed in 
        ~/.oscrc:getpac_default_project (if any), followed by the project repos registered with zypper.

    osc in PROJECT PACKAGE
        install PACKAGE from PROJECT.

    Binary packages often have the same name as their source packages, but not always.
    With osc install, PACKAGE names are binary package names. 

    ${cmd_usage}
    ${cmd_option_list}
    """


    apiurl = self.get_api_url()
    args = slash_split(args)
    if len(args) == 0:
      args = expand_proj_pack(args)
      print "proj/pack from current working directory:", args
    platform = None


    # default_platform = 'openSUSE_12.1'
    osc_cache = '/var/tmp/osbuild-packagecache'
    etc_S_r = '/etc/SuSE-release' 
    if len(args) == 1:
    #{
      m = re.match('perl\((.*)\)$', args[0])
      if m:
        # a perlish RPM capability
        args = ( 'perl-' + re.sub('::', '-', m.group(1)), )
        print "obs name -> %s" % args[0]
      elif re.search('::', args[0]):
        # a cpan name
        args = ( 'perl-' + re.sub('::', '-', args[0]), )
        print "obs name -> %s" % args[0]
      all = self._search_projects(apiurl, args[0])
      # [ {'name': 'python-json-rpc-lib', 'repository': 'openSUSE_Factory', 
      #    'package': 'python-json-rpc-lib',  'type': 'rpm', 
      #    'filepath': 'home:/dec16180/openSUSE_Factory/x86_64/python-json-rpc-lib-20090604-5.1.x86_64.rpm', 
      #    'filename': 'python-json-rpc-lib-20090604-5.1.x86_64.rpm', 'project': 'home:dec16180', 
      #    'baseproject': 'openSUSE:Factory', 'version': '20090604-5.1', 'arch': 'x86_64'}, ... ]
      if not opts.no_cache:
          self._find_cached(all, osc_cache)
      ## extract all platforms, then ...
      seen = {};
      arch_words = self._read_system_name(etc_S_r, opts)
      if (opts.arch is not None): 
        # and nothing else.
        arch_words = [ opts.arch ]
        if opts.arch == 'i386' or opts.arch == 'i586' or opts.arch == 'i686':
          arch_words.append('i586')
          arch_words.append('i686')
          arch_words.append('i386')
        if opts.verbose: print arch_words

      for r in all:
        if opts.verbose:
          print " seen ", r['project'], r['baseproject']
        if r['repository'] == 'standard':
          r['repository'] = re.sub(':','_',r['baseproject'])
        if r['arch'] in arch_words or r['arch'] == 'noarch':
          seen[r['repository']] = 1
      if opts.verbose: print seen
      best = self._best_platform(etc_S_r, seen.keys(), opts)
        
      ## ...filter down by best matching platform
      # my @res = grep { $_->{repository} eq $best } @all;
      ## python: filter() ???
      res = []
      seen = {}
      for r in all: 
        proj_name = r['project']
        if r['repository'] == best and not seen.has_key(proj_name):
          if r['arch'] in arch_words or r['arch'] == 'noarch':
            if proj_name == best:
              res.insert(0,r)
            else:
              res.append(r)         # list each project only once, with best matching arch.
            seen[proj_name] = 1

      if not res:
        raise oscerr.WrongArgs('Could not find %s.\n(Use two args to avoid searching, try --arch, --platform, or try another build service).' % args[0])

      i = 1
      for r in res:
        cached = ''
        if r.has_key('cached'): cached = ' (cached %s)' % (r['cached']['size'])
        print "%2d: %-50s%-15s %-10s%s" % (i, r['project'], r['version'], r['arch'], cached)
        i += 1
      print ''
      if opts.arch:
        print "WARNING: --arch option is unreliable. zypper might still choose something different!"
      
      if len(res) > 1:
        nr = self._user_prompt("Type number from above list (default=1), press ENTER", None, None)
      
      idx = 0
      try:
        idx = int(nr) - 1
        args = [ res[idx]['project'], res[idx]['name'] ]
      except:
        idx = 0
        args = [ res[0]['project'], res[0]['name'] ]

      try:
        args[1] = res[idx]['cached']['path']
        print >>sys.stderr, 'using %s' % args[1]
      except:
        print >>sys.stderr, 'using %s/%s' % (args[0], args[1])

    #}
            
    ## FIXME:
    ## if there is only one argument, and it ends in .ymp
    ## then fetch it, Parse XML to get the first
    ##  metapackage.group.repositories.repository.url
    ## and construct zypper cmd's for all
    ##  metapackage.group.software.item.name
    ##
    ## if args[0] is already an url, the use it as is.

    dl = 'http://unknown.donwload.server(%s)/' % apiurl
    if apiurl == 'https://api.opensuse.org':
        dl = 'http://download.opensuse.org/repositories'
    if apiurl == 'https://api.suse.de':
        dl = 'http://download.suse.de/ibs'
    if apiurl == 'https://pmbs-api.links2linux.org':
        dl = 'http://pmbs.links2linux.org/download'
        # FIXME: home projects are not there, unfortunatly

    ## FIXME: what an ugly hack!
    if apiurl == 'https://api.opensuse.org' and args[0] == 'openSUSE:Factory':
      url = 'http://download.opensuse.org/distribution/openSUSE-current/repo/oss'
    elif apiurl == 'https://api.opensuse.org' and args[0] == 'openSUSE:11.3':
      url = 'http://download.opensuse.org/distribution/11.3/repo/oss'
    elif apiurl == 'https://api.opensuse.org' and args[0] == 'openSUSE:11.4':
      url = 'http://download.opensuse.org/distribution/11.4/repo/oss'
    elif apiurl == 'https://api.opensuse.org' and args[0] == 'openSUSE:12.1':
      url = 'http://download.opensuse.org/distribution/12.1/repo/oss'
    elif apiurl == 'https://api.opensuse.org' and args[0] == 'openSUSE:11.3:NonFree':
      url = 'http://download.opensuse.org/distribution/11.3/repo/non-oss'
    elif apiurl == 'https://api.opensuse.org' and args[0] == 'openSUSE:11.4:NonFree':
      url = 'http://download.opensuse.org/distribution/11.4/repo/non-oss'
    elif apiurl == 'https://api.opensuse.org' and args[0] == 'openSUSE:12.1:NonFree':
      url = 'http://download.opensuse.org/distribution/12.1/repo/non-oss'
    elif apiurl == 'https://api.opensuse.org' and args[0] == 'openSUSE:Factory:NonFree':
      url = 'http://download.opensuse.org/distribution/openSUSE-current/repo/non-oss'
    else:
      repos = get_repositories_of_project(apiurl, args[0])
      # print "get_repositories_of_project(%s,%s) returns " % ( apiurl, args[0])
      # print repos
      platform = self._best_platform(etc_S_r, 
        get_repositories_of_project(apiurl, args[0]), opts)
      url = "%s/%s/%s" % (dl, re.sub(':',':/',args[0]), platform)

    if args[1][0] == '/':
        # zypper bug: with -p url, url is always refreshed, our --no-refresh is ignored.
        # hence without -p url; use --no-cache if dependencies fail.
        cmd = "sudo zypper --no-refresh -v in --force %s" % args[1]
        cmdv = ['sudo', 'zypper', '--no-refresh', '-v', 'in', '--force', args[1]]
    else:
        cmd = "(repo=%s; sudo zypper -p $repo --gpg-auto-import-keys --no-refresh -v in --force --from $repo %s)" % (url, args[1])
        cmdv = ['sudo', 'zypper', '-p', url, '--gpg-auto-import-keys', '--no-refresh', '-v', 'in', '--force', '--from', url, args[1]]

    print "Suggested installation command: \n" + cmd
    all = str(TeePopen(['sudo', 'zypper', 'lr', '-e', '-'], silent='.'))
    if all.find('baseurl='+url) > 0:
      print "repo %s was already added." % url
    else:
      print "(Type 'a' to add the repo permanently) Press Enter to continue."
      a = sys.stdin.readline()
      if a.find('a') >= 0:
        # all = subprocess.Popen(['sudo', 'zypper', 'lr', '-e', '-'], stdout=subprocess.PIPE).communicate()[0]
        all = str(TeePopen(['sudo', 'zypper', 'lr', '-e', '-'], silent='.'))
        if all.find('baseurl='+url) > 0:
          print "is already there, enabling it."
          p = subprocess.Popen(['sudo', 'zypper', 'mr', '-e', url])
          os.waitpid(p.pid, 0)
        else:
          p = subprocess.Popen(['sudo', 'zypper', 'ar', url, 'obs://'+args[0]])
          os.waitpid(p.pid, 0)

    # FIXME:
    # we should temporarily add all the layered repositories from the project.
    # so that dependencies get expanded just the same way as the 11-click-install via web-interface does.
    #
    # We need a way to monitor what the command is printing. Without delaying, prompts and such.
    # subprocess communicate() delays everything.
    if platform is None: platform = 'PLATFORM'

    # old code: os.execvp(cmdv[0], cmdv)
    buf = str(TeePopen(cmdv, verbose=True))
    if opts.prefer_unpublished or re.search("Package '\S+' not found", buf):
      import osc.build
      import tempfile

      ## FIXME: dependencies are not resolved here...o
      ## very likely to run into somehting like this:
      # Forcing installation of 'glade3-3.7.0-8.1.i586' from repository 'Plain RPM files cache'.
      # Problem: nothing provides libgladeui-1.so.9 needed by glade3-3.7.0-8.1.i586
      ##
      print "not there, ... trying unpublished (CTRL-C to abort) Press Enter to continue."
      a = sys.stdin.readline()
      binaries = get_binarylist(apiurl, args[0], platform, osc.build.hostarch, package=args[1], verbose=True)
      # [publican-2.3-15.26.noarch.rpm, publican-2.3-15.26.src.rpm]
      # [copyfs-1.0-1.1.i586.rpm, copyfs-1.0-1.1.src.rpm, rpmlint.log]
      ## weed out non-binaries.
      binaries = filter(lambda x: not re.search('(src\.rpm|\.log|\.xml)$', str(x)), binaries)
      ## sort shortest name is first, so that foo-debuginfo comes after foo
      binaries.sort(lambda x, y: cmp(len(str(x)), len(str(y))))
      ## filter down for starting with my name, optional.
      mainbin = filter(lambda x: re.match(args[1], str(x)), binaries)
      mainbin.extend(binaries)
      if len(mainbin) > 0:
        tmpfile = tempfile.mktemp(suffix='-'+str(mainbin[0]))
        get_binary_file(apiurl, args[0], platform, osc.build.hostarch, str(mainbin[0]), 
                package=args[1], target_filename=tmpfile)
        TeePopen(['sudo', 'zypper', '--no-refresh', '-v', 'in', '--force', tmpfile], verbose=True)
        os.unlink(tmpfile)
      else:
        print "There is no %s for you." % args[1]
    print "\n -- osc %s, by jw@suse.de" % OSC_INS_PLUGIN_NAME


def _read_system_name(self, file, opts):
    print "using %s to match build platforms" % file
    text = open(file).read()
    a = {}
    for i in (re.split("[\s_:=\(\)]+", text)):
      a[i] = 2
    for i in (re.split("[\s:=\(\)]+", text)):
      a[i] = 3
    if a.has_key(''): del a['']

    if a.has_key('i386') and not a.has_key('i586'): a['i586'] = a['i386'] - 1
    if a.has_key('i386') and not a.has_key('i686'): a['i686'] = a['i386'] - 1
    if a.has_key('i586') and not a.has_key('i386'): a['i386'] = a['i586'] - 1
    if a.has_key('i586') and not a.has_key('i686'): a['i686'] = a['i586'] - 1
    if a.has_key('i686') and not a.has_key('i386'): a['i386'] = a['i686'] - 1
    if a.has_key('i686') and not a.has_key('i586'): a['i586'] = a['i686'] - 1
    
    # SUSE Linux Enterprise Desktop 11 (x86_64)
    # VERSION = 11
    # PATCHLEVEL = 1
    ###################
    # -> SLE_11_SP1
    m = re.match('SUSE\s+Linux\s+Enterprise\s+(\w+)\s+(\d+)\s', text, re.I)
    if m:
      v = m.group(2)
      s = 'S'
      if m.group(1) == 'Desktop': s = 'D'
      a['SLE' + s + '_' + v] = 4
      a['SLE'       '_' + v] = 4
      m2 = re.search('^PATCHLEVEL\s*=\s*(\d+)', text, re.I | re.M)
      if m2:
        sp = m2.group(1)
        a['SLE' + s + '_' + v + '_SP' + sp] = 5
        a['SLE'       '_' + v + '_SP' + sp] = 5

    if opts.verbose: print "_read_system_name(%s) -> '%s'" % (file, a)
    self.system_name_words = a
    return a

def _best_platform(self, etc_suse_release, repos, opts):
    """
    given an etc_suse_release file, or a plain platform name (repository)
    this compares a list of repos, and returns the one which literally matches best.
    It also compares with conf.config['build_project'] and gives sanity warnings.

    etc_suse_release is ignored, if platform is not None.
    """
   
    default_platform = 'openSUSE_12.2'
    platform_in = opts.platform
    if opts.verbose:
      print "_best_platform: etc_suse_release=%s, platform_in=%s, repos=%s" % (etc_suse_release, platform_in, repos)
    if platform_in:
      platform_words = { platform_in: 1 }
    else:
      if hasattr(self, 'system_name_words'):
        # initialized by calling _read_system_name() earlier.
        platform_words = self.system_name_words
      else:
        platform_words = self._read_system_name(etc_suse_release, opts)
      platform_words['standard'] = 1      # a fallback

    platform = None
    build_platform = None
    if conf.config.has_key('build_project'):
      build_platform = conf.config['build_project']

    max_score = 0
    if len(repos):
      for i in (range(0,len(repos))):
        score = self._matches_in_name(repos[i], platform_words)
        if opts.verbose:
          print "repo %s: score %s" % (repos[i], score)
        if score > max_score:
          max_score = score
          platform = repos[i]
    if build_platform:
      score = self._matches_in_name(build_platform, platform_words)
      if score > max_score:
        if (platform and build_platform != platform):
          print "CAUTION: .oscrc:build_project %s disagrees with best matching platform %s" % (build_platform,platform)
        else:
          platform = build_platform
      if score < max_score:
        print "CAUTION: .oscrc:build_project %s does not match: low score=%d" % (build_platform, score)

    if platform:
      print "Best matching platform is %s" % platform
      if opts.platform and opts.platform != platform:
          platform = opts.platform 
          print "cmdline takes precedence: -p %s" % opts.platform
    else:
      platform = default_platform
      print "Default platform=%s (no scores). Use 'build_project' in ~/.oscrc or -p to override" % platform
    return platform


def _matches_in_name(self, name, words):
    """
    words is a dictionary of keywords with score values. Name is matched against each word.
    A word can score up to 4 times: infix, prefix, suffix or exact match.
    Any left-over wordlike tokens in name count (slightly) against the score.
    """
    score = 0
    remainder = name

    for m in words.keys():
        remainder = re.sub(re.escape(m), '', remainder)
        if name.find(m) >= 0:  score += 10 * words[m]
        if name.startswith(m): score += 10 * words[m]
        if name.endswith(m):   score += 10 * words[m]
        if name == m:          score += 10 * words[m]

    if len(remainder):
      remainder = re.sub('[ _:]+', ' ', remainder)
      # if opts.verbose:
      #   print "%s left-over pieces: %s" % (name, remainder.split())
      score -= len(remainder.split())

    return score


def _prefered_projects(self, apiurl):
#{
    if len(conf.config['getpac_default_project']):
      candidates = re.split('[, ]+', conf.config['getpac_default_project'])
    else:
      candidates = []
    prio = {}
    n = len(candidates)
    for c in candidates:
      prio[c] = n
      n -= 1
    return prio
#}

def _find_cached(self, all, osc_cache):
  for r in all:
    # /var/tmp/osbuild-packagecache/devel:languages:perl/openSUSE_11.3/i586/perl-macros-1.0-14.1.i586.rpm
    path = '/'.join([osc_cache, r['project'], r['repository'], r['arch'], r['filename']])
    st = None
    try: st = os.stat(path)
    except: pass
    if st: r['cached'] = { 'size': st.st_size, 'path': path }

def _search_projects(self, apiurl, packname):
  pref = self._prefered_projects(apiurl)

  # GET https://api.opensuse.org/search/published/binary/id?match=@name='file_unpack'
  # <collection matches="4">
  #   <binary name="file_unpack" project="devel:languages:perl" 
  #    arch="noarch" filename="file_unpack-0.37-4.1.noarch.rpm" 
  #    filepath="devel:/languages:/perl/openSUSE_11.2/noarch/file_unpack-0.37-4.1.noarch.rpm" 
  #    baseproject="openSUSE:11.2" type="rpm" />
  #...
  xpath = "@name='%s'" % packname

  # DOESNOTWORK: search cannot have keywords with slashes.
  # collection = search(apiurl, 'published/binary/id'=xpath)
  query = { 'match': "@name='%s'" % packname }
  u = makeurl(apiurl, ['search', 'published', 'binary', 'id'], query)
  print u
  f = http_GET(u)
  collection = ET.parse(f).getroot()
  found = []
  for f in collection.findall('binary'):
    found.append(f.attrib)
  found.sort(key=lambda e: (-pref.get(e['project'],0), e['project'], e['repository']))
  return found

## namespace clash: same method in osc-legal.py
def _user_prompt(self, prompt, msg, injected):
    if msg is not None: msg = msg.rstrip()
    if injected:
      if msg is not None: return msg + "\n" + injected
      return injected
    print prompt
    if msg is not None: print "> " + msg
    sys.stdout.write("> ")
    response = sys.stdin.readline().strip()
    if msg is not None: response = msg + "\n" + response
    return response

class TeePopen():
  """
  A popen-like redirector, that does not suffer from unexpected buffering.
  It uses a PTY, to make the subprocess believe it is connected to a terminal, 
  rather than a pipe. There are several disadvantages involved in this technique: one, the
  pty module lacks signal handling; second, stderr/stdout cannot be distinguished.
  """
  def __init__(self, cmdv, tee_fd=None, silent=False, verbose=False):
    if tee_fd is None:
      self.tee = StringIO()
      self.internal_fd = True
    else:
      self.tee = tee_fd
    if silent == True:
      self.silent = ''
    else:
      self.silent = silent
    if verbose:
      print '+', ' '.join(cmdv)
    #
    ## python lambda is the only way to look into the surrounding scope. 
    ## But then python lambda cannot do anything except a simple expression.
    ## hence we need both 
    ## a method
    ##  which can have assignments and multiple statements, but cannot see the scope.
    ## and a lambda
    ##  which sees the scope, but cannot have assignements and multiple statements.
    ## and we need to pass in a reference, so that it is mutable from inside.
    ##  using a one element array.
    ## Total: three ugly hacks, that would be a plain anonymous sub {} in perl.
    import pty

    # FIXME: this code has better signal handling than pty.spawn:
    # http://code.google.com/p/lilykde/source/browse/trunk/runpty.py?r=314
    pty.spawn(cmdv, lambda fd: self.tee_read(fd))
  def tee_read(self, fd):
    """ 
    subclass and overwrite this, if a tee'ing to a file-like object is inadequate 
    tee_read is called whenever fd was found readable. fd is the masterside of a PTY.
    """
    r = os.read(fd, 1024)
    self.tee.write(r)
    ## haeh, why is the ternery operator so ugly in python???
    return (r, self.silent)[self.silent != False]
  def __str__(self):
    if self.internal_fd:
      return self.tee.getvalue()
    else:
      return self.tee
  def __del__(self):
    if self.internal_fd:
      self.tee.close()
globals()['TeePopen'] = TeePopen

