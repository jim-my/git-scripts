#!/usr/bin/env ruby
# encoding: utf-8
#
# find all commits with two parents(merges)
#

cmd = 'git log --min-parents=2'
puts '> ' + cmd
system cmd
