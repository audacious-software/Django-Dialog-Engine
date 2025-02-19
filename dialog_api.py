# pylint: disable=line-too-long

def identify_script_issues(script): # pylint: disable=too-many-branches
    issues = []

    for node in script.definition: # pylint: disable=too-many-nested-blocks
        if node['type'] == 'random-branch':
            actions = node.get('actions', [])

            node_name = node.get('name', None)
            node_id = node.get('id', None)

            if len(actions) == 0: # pylint: disable=len-as-condition
                issues.append(('error', 'Random branch node "%s" (%s) has no configured actions.' % (node_name, node_id),))
            else:
                for action in actions:
                    destination = action.get('action', None)

                    if destination is None:
                        issues.append(('error', 'Random branch node "%s" (%s) contains branch pointing to a null destination.' % (node_name, node_id,),))

                    if destination == node_id:
                        issues.append(('error', 'Random branch node "%s" (%s) contains branch pointing back to itself.' % (node_name, node_id,),))

        if node['type'] == 'branch-prompt':
            node_id = node.get('id', None)
            node_name = node.get('name', None)

            timeout = node.get('timeout', None)

            if timeout is not None:
                timeout_node_id = node.get('timeout_node_id', None)

                if timeout_node_id is None:
                    issues.append(('error', 'Branching prompt node "%s" (%s) contains a timeout pointing to a null destination.' % (node_name, node_id,),))
                else:
                    found = False

                    for test_node in script.definition:
                        if timeout_node_id == test_node.get('id', None):
                            found = True

                            break

                    if found is False:
                        issues.append(('error', 'Branching prompt node "%s" (%s) contains a timeout pointing to a non-existent destination (%s).' % (node_name, node_id, timeout_node_id,),))

    return issues
