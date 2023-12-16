#!/usr/bin/env ruby

def usage
    'Usage: git-review REPO BRANCH BASE_BRANCH'
end
repo = ARGV.shift || abort(usage)
branch = ARGV.shift || abort(usage)
base_branch = ARGV.shift || abort(usage)
branch_local = "#{repo}-#{branch.gsub('/', '_')}"

repo_origin = `git config --get remote.origin.url`.strip
repo_url = `git config --get remote.#{repo}.url` 
if repo_url.empty?
    puts "Repository #{repo} not found! Please add it using something like:\n\tgit remote add #{repo} #{repo_origin}"
    exit 1
end

cmds = []
if `git rev-parse --verify #{branch_local}`.to_s.length > 0
    puts "Existing branch:"
    cmds << "git checkout #{branch_local}" 
    cmds << "git pull #{repo} #{branch}" 

    cmd = cmds.join(' && ')
    puts '> ' + cmd
    system(cmd) || abort("Error: Failed to run #{cmd}")
else
    cmd = "git fetch #{repo} #{branch}"
    # cmd = "git fetch #{repo} refs/pull-requests/#{pr_id}/from:#{branch_local}-pr#{pr_id}"
    puts '> ' + cmd
    system cmd || abort("Error: Failed to run #{cmd}")

    cmd = "git checkout -b #{branch_local} #{repo}/#{branch}" 
    # cmd = "git checkout -b #{branch_local}-pr#{pr_id}" 
    puts '> ' + cmd
    system(cmd) || abort("Error: Failed to run #{cmd}")
end


cmd = "git-review-phpstan #{base_branch}"
puts '> ' + cmd
system cmd
