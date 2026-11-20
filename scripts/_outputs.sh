# shared helper: read a CloudFormation output
STACK=${STACK:-exam-platform}
out() { aws cloudformation describe-stacks --stack-name "$STACK" \
        --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
