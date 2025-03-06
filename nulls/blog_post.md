---
title: How Language Models Understand Nullability
author: '[Alex Sanchez-Stern](https://www.alexsanchezstern.com) and [Anish Tondwalkar](https://ani.sh)'
date: '$d_{model}$'
header-includes:
  - "<script src=\"sidenotes.js\"></script>"
bibliography: all.bib
linkReferences: true
abstract:

  Large language models have demonstrated an emergent ability to write
  code, but this ability requires an internal representation of
  program semantics that is little understood. Recent interpretability
  work has demonstrated that it is possible to extract internal
  representations of natural language concepts, raising the
  possibility that similar techniques could be used to extract program
  semantics concepts. In this work, we study how large language models
  represent the nullability of program values. We measure how well
  models of various sizes complete programs that use nullable values,
  and then extract an internal representation of nullability.

---

# Introduction

The last five years have shown us that large language models, like
ChatGPT, Claude, and DeepSeek, can effectively write programs in many
domains. This is an impressive capability, given that writing
programs involves having a formal understanding of
program semantics. But though we know that these large models
understand programs to an extent, we still don't know many things
about these models' understanding. We don’t know where they have deep
understanding and where they use heuristic reasoning, how they
represents program knowledge, and what kinds of situations will
challenge their capabilities.

Fortunately, recent work in model interpretability and representation
engineering\AT{reframe. recent tools let us....} has produced promising results which give
hope towards understanding more and more of the internal thought
processes of LLMs. Here at $d_{model}$ , we can think of no better
place to apply these new techniques than formal methods, where
there are many abstract properties that can be extracted with static
analysis. The vast work done in programming language theory over the
past hundred years provides many tools for scaling an understanding of
the internal thought processes of language models as they write
code.\AT{for examples, see cite, cite}

In that spirit, we wanted to start with a simple property that comes
up in every programming languages, nullability. Nullable values are
represented differently across languages; as null pointers in C or
C++, with explicit Option types in Rust, and with special nil or None
values in dynamic languages like Javascript, Lisp, or Python. In every
case, understanding where values can be nullable is necessary for
writing even basic code, and misunderstanding where they are nullable
can often be a source of bugs.

Do our models understand when a value is nullable? They must, to be
able to write code that deals with nullable values, but we haven’t
known what form this knowledge takes, what situations are likely to
confuse the model. Until now.\todo{big claim!}

In this work:

* We introduce a microbenchmark of 15 programs that test basic model
  understanding of the flow of nullability through a program.

* We find that models begin to understand nullability in a local
  scope, satisfying many requirements of the python typechecker,
  before they start to understand how nullability flows across the
  program. ([@Sec:testing])

* We find that models develop an internal concept of nullability as
  they scale up and are trained for longer. ([@Sec:probing])

We end with a demo: after we train a probe that uses the
determines whether the model thinks a variable
read corresponds to a nullable variable, we can demonstrate that internal
knowledge in a reading diagram:

![A diagram showing a simple program, and the probes nullability
 predictions for each variable load.](images/reading_diagram.svg){#fig:reading1 .inlinefig}

# Measuring Nullability Understanding Externally {#sec:testing}

We begin with a "skyline" estimate of model understanding of nullability
(a la @feng24binding).
That is, we evaluate model nullability understanding externally,
at the token-level, (as opposite to internally, at the activation level,
using interpretability techniques). In this section, we first
explain the task of nullability understanding ([@Sec:task]). Then
we formally decompose the reasoning steps required to reason about
nullability both inside ([@Sec:intra]) and across ([@Sec:inter]) functions.
Finally, we present the results of our "skyline" analysis. ([@Sec:eval_results]).

## `NullabilityEval` {#sec:task}

To measure nullability understanding externally, we ask the model to
complete simple partial programs that each require an understanding of
nullability. We refer to this suite of programs as
`NullabilityEval`. All of the tests in this benchmark suite are
composed of three functions or less, where the largest function is
seven lines long.

In our experiments we focus on the Pythia model suite [@biderman23],
as they have checkpoints available across training runs and various
scales. For measuring performance at larger sizes, we also include
Qwen2.5-Coder-32b\AT{cite}, Llama 3.1 405b Instruct\AT{cite}, and
DeepSeek-V3 (671b)\AT{cite}.

Each partial program is constructed such that there are a very limited
number of valid next lines in the program, and all of them demonstrate
some knowledge of the concept of nullability.

For example, our first test is:

*Test 1*^[The loop indicates that the
next few lines need to process `num` in some way, and the fact that it
comes from `some_numbers` means it has the type `Optional[int]`. `num`
can’t be directly appended to `result`, because `result` is declared
to only contain `int`s, not `Optional[int]`s. None of the normal
operations on `int`s will work on `None`s, so before `num` can be
processed, something has to be done to separate `None`s and normal
`int`s.]
```python
def main() -> None:
  some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
  result: list[int] = []
  for num in some_numbers:
```

We would like the mode to generate code that performs some operation on the elements of `some_numbers`.
The simplest way to do that is to introduce a branch `if num is None`,
but several variants are also valid: `if num is not None`, `if num ==
None`, `if isinstance(num, int)`. That is, this example is constructed such
that there is a small space
of valid next lines, and all of them require some understanding that
`num` may not be an `int`.^[In particular, we can use this program to test models for
nullability understanding by asking them to complete the program's next lines, then see if those lines matches the regular expression
`num\s*(is\s*(not)?|==)\s*None|isinstance\(num`.]

## Understanding Typing Rules {#sec:intra}

We find that Pythia models as small as 2.8b can successfully complete
Test 1, and that they learn to complete the test in the first third of
training. Consistent with observations that larger models are more
sample-efficient \AT{who do I cite for this claim? Kaplan?}, larger
Pythia models learn to complete this test earlier, with Pythia 12b
able to complete the test 20% of the way into training and Pythia 2.8b
able to complete it 28% of the way into training.^[Note that these
results differ substantially from those of @tigges24, who find that
for _circuit_ analyses (rather than representational analyses like
ours), circuit parts are learned at roughly the same point during
training across scale.]

These results indicate that these models understand nullability to
some extent, but how deep is this understanding? To quantify this, we
give a syntax and semantics of a minimalist subset of python that
captures nullability in Appendix [B](#sec:formalrules). We can then
classify each partial program by which program constructs and rules
determine the nullability of the target variable. For instance, Test 1
uses the $(List)$, $(Var)$, and $(For)$ rules.

So, do Pythia models 2.8b and up understand the semantics of these
three rules? As it turns out, not exactly. LLM's pick up on a lot of
information relationships in their training data that have statistical
correlation, without it necessarily being causal. What this means in
practice is that the models use things like variable names,
whitespace, statement orderings, and constant values to guess at
certain programming concepts.

For example, while many of the Pythia models
can complete:

```python
some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
result: list[int] = []
for num in some_numbers:
```

with a proper None check, changing the variable names and the
constants into:

```python
foo = [60, None, -33]
bar: list[int] = []
for corejoice in foo:
```

causes all the Pythia models to fail the test.

To test the reliance on these features more robustly, we generated 100
random variable namings and constant values for the above program, as
well as for small program that test other typing rules. We also
balanced these tests with programs that made use of the same language
constructs, but where the loop variable was *not* optional. We found
that when lists and for loops were involved, Pythia 2.8b was only able
to correctly label 57% of the programs, only slightly better than
chance. Even Pythia 12b could only correctly label 68% of the
tests. These results show that the Pythia models rely heavily on these
non-semantic features when reasoning about for loops.

Fortunately, many other typing rules do not exhibit such a strong
reliance on variable naming and constants. In the same setting of
generated programs, we found that Pythia 2.8b was able to correctly
label programs using the Abs, Var, App, and If_Out a much greater
proportion of the time (99%, 93%, 86%, and 98% respectively). Stay
tuned in the future ([@Sec:future]) for a more in-depth exploration of
how the models behave on individual typing rules when we increase the
variability of our program generation.

## Interprocedural Analysis {#sec:inter}

We can further challenge the model by adding layers of procedural indirection
between the source and sink of nullable values, thereby testing the model's
_interprocedural_ understanding. First, we demonstrate how to write such tests,
and the difficulties of writing tests that may be too easy ([@Sec:inter_test]).
Then, we present a harder problem ([@Sec:unannot]) and introduce a stronger type system `mypy++` to formalized the needed reasoning ([@Sec:mypypp]).

### A simple test {#sec:inter_test}

Here's a simple test for interprocedural analyses:

*Test 2*
```python
from typing import Optional

def main() -> None:
    some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
    print(positive_numbers(some_numbers))

def positive_numbers(numbers: list[Optional[int]]) -> list[int]:
    result: list[int] = []
    for num in numbers:
```

In this test, we've taken the same logic and spread it across `main`
and another function, `positive_numbers`. Ideally, the model would
have to think a little harder to understand that `some_numbers` is
flowing from `main` through the function call into the body of
`positive_numbers`, causing the for loop body to need a `None`
check. In practice, however, we find this test is actually *easier* for
the model to pass than Test 1, with models as small as Pythia 1b
passing it, and Pythia 12b learning to pass it 13% of the way into
training.

Because of the type annotations on the `positive_numbers` function,
the model doesn't need to pay attention to `main` at all. It can just
look at `positive_numbers`, and use the type annotation to know that
`numbers` contains `Optional[int]`s. Then, using the For rule it can
reason that `num` is nullable, so it must be checked for None before
proceeding. Looking at the type annotation turns out to be easier for
the model than scanning through a list to determine if there are None
and non-None values, resulting in an easier test overall.

### Unannotated Functions {#sec:unannot}

So how would we *actually* test for interprocedural nullability
understanding in the model? Well, type annotations on Python functions
aren't required^[Technically this is known as "Optional typing", but
that's confusing in the context of this post. Not to be confused with
Gradual Typing, as introduced by Siek et al.], so we can instead
provide the model with an **unannotated** function, and see if it
still understands the flow of nullability. Here's a test that does
that:

*Test 3*
```python
def main(x: int) -> None:
    if x > 0:
        value = "*" * x
    else:
        value = None

    x = process_value(value) + 1
    print(x)

def process_value(value):
```

Our base set of typing rules (listed as "Common Rules" in Appendix
[B.1](#sec:commonrules)) don't handle unannotated functions though, so
we're going to have to add some more, and here we're faced with a
choice. The typing rules for normal Python say that functions without
return type annotations return the Any type, and arguments without a
type annotation have the type Any. In fact, normal mypy will not check
unannotated functions at *all*, even for internal consistency; the
`--check-untyped-defs` option will add some checking back, but the
types of arguments and return type will still be Any. In Python, a
value of any type can be converted to an Any, and an Any can be
converted to any value type.

This means that it would be technically type safe to do anything in
the body of `process_value`, including just returning the argument,
without a static type error. All Pythia models with at least 410
million parameters are able to make use of this extra flexibility to
write code for Test 3 that typechecks under mypy. But at runtime, code
that exploits it would still fail.

### A stricter type system for Python: mypy++ {#sec:mypypp}

If we want code that does not `TypeError` at runtime, we can
strengthen our type checker by requiring that there be some valid,
non-`Any`, type for the function that typechecks at the call site and
in the function body. This new typechecker is still checking
unannotated functions, but passing fewer of them. We'll call this
augmented type system mypy++.

In Appendix [B.2](#sec:unannotatedfuncs), we formalize the unannotated
function rules for mypy vs mypy++.

There's no consistent threshold of size at which Pythia models can
pass Test 3. Pythia 1b, 2.8b, and 6.9b pass the test in their final
revisions, but Pythia 410m, 1.4b, and 12b don't. The models with at
least 1 billion parameters all have points in training where they can
pass the test, but only intermittently. Even 6.9b, the best performing
size on this test, fails the test in its second-to-last available
revision^[Despite this, it does pass the test 40% of the available
revisions, about triple what the other closest sizes can
accomplish]. You can see how this evolves over scale in @fig:hl_mypy
and time in @fig:hl_moral.  See @Sec:results for further discussion of
performance over time.

What the models *can* do well, however, is learn to pass these tests
in the mypy type system (as opposed to mypy++). In that system, where
they don't need to reason globally about the functions but only
locally, this test is one of the easiest for the models to
complete.^[This indicates that if you were to train a model using
typechecking as reinforcement feedback, you would want to use mypy++
and not mypy.]

Since this test suite is meant to be informative beyond the sizes of
the Pythia models, we also add another layer of indirection to add
more difficulty, in this test:

*Test 4*
```python
def handle_value(value, guard):
    if guard:
        return process_value("Foobar") + 1
    else:
        return process_value(value) + 1
def main(x: int) -> None:
    if x > 0:
        value = "*" * x
    else:
        value = None

    x = handle_value(value, x < 10)
    print(x)

def process_value(value):
```

In Test 4, instead of `main` calling `process_value` directly, it
calls `handle_value`, which itself calls `process_value` in a
branch. With two layers of indirection, we start to hit the limits of
the capabilities of even frontier models. Llama 405b is unable to
successfully pass this test, as are smaller models like Qwen Coder
32b, while DeepSeek V3 (671b parameters) is able to pass it. However,
Pythia 6.9b is still able to pass this test pretty consistently.

## Generating Type Annotations

Finally, we can test how well the models write write type
annotations for functions. Here, the trailling colon makes
the type expression the only valid completion.

*Test 5*:
```python
def program_48() -> None:
  number: Optional[int] = None
  square = get_square(number)
  if square is not None:
    print(f"Square of the number is {square}")
  else:
    print("No number provided to square")

def get_square(number:
```

None of the Pythia models pass this test. Qwen Coder 32b is
also incapable of passing this test, but both Llama 405b and DeepSeek
V3 pass it.

We would indeed expect that writing type annotations is more difficult than merely
implicitly reasoning about the types of python programs, as only a small
fraction of python programs in the wild are thus annotated.

## External Test Results Across Training and Scale {#sec:eval_results}

We wrote three variations of each of these tests, resulting in 15
tests total. Below, you can see the number of passing tests for each
model.
\AT{should we be plotting lpr? instead of raw pass rate? but log 15 is pretty small...}

![A bar graph showing how several sizes of model perform on the
 high-level nullability tests](images/hl_model_results.svg){#fig:hl_scale}

In [@Fig:hl_scale], we can see the number of passing tests for each
model. We can see that, generally speaking, models get better with scale: Pythia-2.8b
parameters can pass about half the tests, but we need the much larger and more
parameter efficient Llama-405b to pass all of the tests. This matches our expectations
that eval scores should scale logarithmically, indicating that these tests are well distributed.

![A bar plot showing how the Pythia models perform in mypy vs
 mypy++](images/hl_mypy_vs_grep_models.svg){#fig:hl_mypy}

\todo{let's merge these figures}
In [@Fig:hl_mypy], we see the test result for the pythia models
using the mypy and mypy++ type systems.
As we expected, the mypy results (red bar) are always above
the mypy++ results (blue bar), as mypy++ is a stricter type
system. There are six tests in the dataset involving non-annotated
functions, and using the weaker mypy typesystem causes up to five more
tests to pass than using mypy++^[We don't see all six non-annotated
function tests passing under mypy, because models can still fail these
tests by producing invalid syntax.]

Next, we want to understand the training dynamics at play here. Below,
we can see how Pythia 6.9b performs on the tests during training from
step 2 to 143000: ^[smoothed with a rolling average with a window size of 5]

![A plot showing how often the Pythia 6.9b produces code that
typechecks on the tests, vs produces code that does not go wrong.](images/hl_mypy_vs_grep_revisions.svg){#fig:hl_moral}

We see that each individual model learns to
write code which typechecks under mypy before it learns to write code
which typechecks under mypy++ and throws no type errors at runtime.


# Measuring Nullability Understanding Internally {#sec:probing}

At this point, we’ve figured out how to roughly measure nullability
understanding in the output of various language models, but we still
don’t know what their internal representations might look like or when
they emerge. Next, we detail how we train reading vectors
([@Sec:extraction]), using prompts designed to make the model think
about the phenomena of interest ([@Sec:prompts]). Finally,
in [@Sec:results], we validate that these probes improve their
understanding of nullability over the course of pretraining to the
level that we expect from the external, or token-level understanding
evals we describe in the previous section.

## Background

In this section, we review representation engineering [@zou25] techniques that
we will use to look for linear representations of nullability inside the model.

@zou25 shows how representations can be extracted for
concepts like "happiness", "honesty", and "fairness". First, they
construct many prompts which cause the model to act in a way aligned
with the concept, and many which cause the model to act in a way
aligned against the concept. For instance, they might prompt the model
with "Pretend you’re a dishonest person. The Eiffel Tower is" and
"Pretend you’re an honest person. The Eiffel Tower is". Then, they
take the internal activations which correspond to each, and try to
extract a high-dimensional vector which points towards the states
which are aligned, and away from the states that are not aligned. This
vector can then be used as a linear model to measure how much of the
concept is activated in the model during any given forward pass (e.g. for honesty,
this gives us a lie-detector).
\AT{ formatting citekey in figcap}

![Figure from  @zou25 showing the reading outputs for several
 concepts](images/zhou.png)

## Designing Prompts to Extract Nullability Activations {#sec:prompts}

We avoid dealing with the ambiguities of natural language by working
in a setting where the model needs only to analyze the nullability of
individual variable occurrences. Specifically, we probe for "the
variable I just generated refers to an nullable quantity", so our
prompts looked like:

```python
def program_1() -> None:
  def find_value(data: List[int], target: int) -> Optional[int]:
    for value in data:
      if value == target:
      return value
    return None

  data = [1, 2, 3, 4, 5]
  target = 3
  result = find_value(data, target)
  if result
```

We queried o1, o1-mini, deepseek-coder, and claude-3.5-sonnet with the following prompt:

> Generate me 100 typed python programs that use the Optional type,
> along with type annotations for any undefined functions that they
> use. Make sure that the programs are unique, and each involves at
> least eight lines of logic. Number each program from 1 to 100. Please
> put all the programs in a single file, with a main function that tests
> each. Don't include any text before or after the code, just the
> code. I will be using mypy with the --strict option to check the code.

We label each variable read occurrence with nullability information derived
from mypy, and prompt the "model under test" with a prompt consisting of the
tokens up to and including the variable read occurrence.

## Extracting Reading Vectors {#sec:extraction}

Prior work focused their probing on a single layer, often handpicked
based on prior papers. We probe all layers instead. We use Mass Mean
Shift probing for each layer, because it's been shown empirically
[@li24] to generalize better in high dimensional spaces than logistic
regression^[Since we don't have contrasting pairs, just labeled
points, it's not possible to use the PCA from contrasting pairs method
used in @marks24 and @zou25. See "Mass Mean Probing vs Linear
Regression" in the appendix]. This technique involves taking the means
of each class, and using their difference as the reading vector.

We then tested two methods for determining the relative importance of
the different layers --- either allowing the magnitude of the
difference of means vector to determine the importance of the layer in
the final probe (MM), or to learn coefficients for each layer using
linear regression (MM-LR). We found that which method is more accurate
on test data varies over both model size and number of training steps.
\AT{should we mention this in the intro/contributions/or a "key
results" section like tlide?}

![The performance of pure mass means shift vs mass means shift
 with linear regression for different Pythia model sizes. Lower is
 better.](images/mm-vs-mmlr.svg){#fig:mm-vs-mmlr-sizes}

In [@Fig:mm-vs-mmlr-sizes], we can see that pure mass means probing
\AT{add a y axis label for BCE. This should probably be a line plot.}
gives lower loss for smaller models (those with less than 410 million
parameters), but that for larger models weighting layers using linear
regression gives lower loss consistently.

## Visualizing Probe Outputs

Let us return to the reading diagram from the introduction, reproduced
below.

This diagram is adapted from the style of reading diagram from @zou25, but only
show the activations on tokens that represent variable loads^[This is, of course, where we trained our probes, but there is also a practical
reason: right after the model has generated a variable that will be
written to, it often does not have access to the assigning expression
or type annotation, giving it no way to determine if the value will be
optional or now.]. For each position of interest, we prompt the model with the
partial program that consists of all tokens up to (preceeding) and including
that position. We then probe the model at the following token. We color the box above that position
based on the output of the probe, and a scoring threshold inferred at
train-time^[Red tokens are significantly below the threshold, and
green tokens are significantly above it; tokens that scored near the
threshold would have a near-white color, but no such tokens appear in
this example.].

![A diagram showing a simple program, and the probes nullability
 predictions for each variable load.](images/reading_diagram.svg){#fig:reading2 .inlinefig}

In this program, there are sixteen tokens that correspond to variable loads,
and (correctly) all but one are marked as non-optional.
The only nullable variable in this program is `result`,
since it comes from `find_value` which returns `Optional[int]`.^[When this variable appears for the first time, it is in the `if` statement
that checks if it's `None`. Then, the model knows it is nullable, and the results
of the probe reflect that understanding. But when it appears a second
time on the next line, in the format string of `print`, the body of this if statement only
runs if it is *not* `None`. The model understand this as well, and the probe accurately reflects this.]

## Probing Results Across Training and Scale {#sec:results}

In this section, we study the performance of our nullability probes across time
and scale [@tigges24].
We use mass-means shift probing [@li24] on all layers,
and a linear regression to determine the weights of each layer.^[
@li24 and @zou25 suggest that mass means probes are best for reading,
while the direction perpendicular to the separating hyperplane is best for
intervention.
However, previous work leaves open the question of cross-layer weights. We use
LR on the cross-layer weights, thanks to our investigations above.]
\AT{see appendix D for mm vs LR}

![The performance (probe test loss) of each Pythia
 model size during pretraining. Lower is
 better.](images/accuracy_during_pretraining.svg){#fig:models-and-steps}

In [@fig:models-and-steps], we plot loss against scale and time.
While we measured accuracy for every available Pythia model size, we exclude
the smallest (14m) from this plot since it would
exist entirely above the top of the plot.

One thing that is interesting to note is that models up to 1b reach
a minimum loss before loss for this task climbing again. Charitably, this may be because the
features beyond this point become more complex --- less linear, or the represented
features themselves represent more subtle concepts. Cynically, this reflects
that models---small models in particular---do not uniformly improve at this task over training, as we observed in @Sec:mypypp.

Our suspicion is that this
pattern would continue even for the larger models if we continued to overtrain them for longer.
\todo{position the min loss stuff in terms of scaling laws or something?}

# Future Work {#sec:future}

We hope to get a better understanding of this phenomenon by studying the
decomposed nullability reasoning as described in @Sec:intra and Appendix [B.1](#sec:commonrules).

# Related Work {#sec:related}

Our decision to use Pythia to study feature evolution across time and scale is
inspired by @tigges24 . They focus on classic circuits-centered
interpretability tasks such as IOI [@wang22], Gendered-Pronoun [@mathwin],
Greater-Than [@hanna23] , and SVA [@linzen16].

In our setting, we are more interested in how activations vary across inputs, to extract
representations of nullability. @zou25 surveys techniques for
representation engineering with linear probes. We apply similar techniques, but
to program semantics and dataflow instead of natural language.

@feng24predicate also study LLM's ability to reason about propositions, but in
a natural language setting, rather than a formal one.

Several techniques exist for constructing linear probes, but after
experimental measurement we followed the mass means shift from @li24. @li24
and @zhong23 discuss why mass mean probing might outperform linear regression.



# References {.unnumbered}
::: {#refs}
:::
