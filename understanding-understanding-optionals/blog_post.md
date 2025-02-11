---
title: Understanding Models Understanding Optionality
author: '[Alex Sanchez-Stern](https://www.alexsanchezstern.com) and [Anish Tondwalkar](https://ani.sh)'
date: '$d_{model}$'
bibliography: all.bib
linkReferences: true
abstract: 'The Abstract\todo{abstract}'
---

# Introduction
The last five years have shown us that Large Language Models can
effectively write programs in many domains.\todo{cite} This is an impressive
capability given that writing programs involves having a working
understanding of many aspects of their semantics. But though we know
that these large models understand programs to an extent, we still
don’t know what form that understanding takes; where it has a deep
understanding and where it uses heuristic reasoning, how it represents
program knowledge, and what kinds of situations will challenge its
capabilities.

Fortunately, recent work in model interpretability and
representation engineering\todo{which work?} has produced promising results
which give hope towards understanding more and more of the
internal thought processes of LLMs. Here at $d_{model}$ , we can
think of no better place to apply these new techniques than
program understanding, where there are many abstract
properties that can be symbolically determined. The vast work
done in programming language theory over the past hundred
years provides many tools for scaling an understanding of the
internal thought processes of language models as they write
code.\todo{for examples, see cite, cite}

In that spirit, we wanted to start with a simple property that comes
up in every programming languages, value optionality.\todo{we need a better word for "optionality"} Optional values
are represented differently across languages, null pointers in C++ or
Java, with explicit option types in Rust, and with special nil or None
values in dynamic languages like Javascript, Lisp, or Python. In every
case, understanding where values can be optional is necessary for even
their most basic uses, and misunderstanding where they are optional
can often be a source of bugs, like a null pointer dereference.

Do our models understand when a value is optional? They must, to be
able to write code that deals with optional values, but we haven’t
known what form this knowledge takes, what situations are likely to
confuse the model. Until now.\todo{big claim!}

With this work, we contribute three things:

* A microbenchmark of 15 programs that test basic model understanding
  of the flow of optionality through a program.

* Experiments that show that models begin to develop a concept of
  optionality as they get bigger and are trained for longer.

* Experiments that show that models begin to understand optionality in
  a local scope, satisfying many requirements of the python
  typechecker, before they start to understand how optionality flows
  across the program.

# Overview

Understanding the flow of optionality across programs is an essential
part of writing most code, and misunderstandings are often a source of
bugs. For models to write code, they must learn to track optionality
in some form. In this work, we'll explore ways to measure optionality
understanding in language models, and use that to show how the
understanding of optionality changes over various model parameters.

## Which Models Understand Optionality?

We begin with a "skyline" estimate of model understanding of optionality
(a la @fengBinding2024), first measure how well different models can
understand the concept. We have the model
complete simple programs that require an understanding of
optionality. We refer to this suite of programs as `OptionalEval`.

To test these models for optionality understanding, we constructed 15
partial program tests. For example,

*Test 4*:
```python
def main() -> None:
  some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
  result: list[int] = []
  for num in some_numbers:
```

This partial program is only four lines, with type annotations. A
`some_numbers` array is created that includes positive numbers, negative
numbers, and None values, giving it type `Optional[int]`. A list `result`j
is constructed to give the model a sense of dataflow,
and then a loop loops over `some_numbers`.

The program is constructed such that there are a very limited number
of valid next lines in the program, and all of them demonstrate some
knowledge of the concept of optionality.^[The loop indicates that the
next few lines need to process `num` in some way, and the fact that it
comes from `some_numbers` means it has the type `Optional[int]`. `num`
can’t be directly appended to `result`, because `result` is declared
to only contain `int`s, not `Optional[int]`s. None of the normal
operations on `int`s will work on `None`s, so before `num` can be
processed, something has to be done to separate `None`s and normal
`int`s.
The simplest way to do this is to introduce a branch `if num is None`,
but several variants are also valid: `if num is not None`, `if num ==
None`, `if isinstance(num, int)`. Since this is a pretty small space
of valid next lines, and all of them imply some understanding that
`num` may not be an `int`, we can use this program to test models for
optionality understanding by asking them to complete the program
another lines, then see if they produce something that matches these
valid lines with the regular expression
`num\s*(is\s*(not)?|==)\s*None|isinstance\(num`.]

This test is on the simpler side, but we can challenge the model more,
adding layers of indirection between the source and sink of optional
values, testing the model's _interprocedural_ understanding.

We can also test how well models understand type annotations
separately; since the inclusion of type annotations in Python is not
required^[Technically this is known as "Optional typing", but that's
confusing in the context of this post. Not to be confused with Gradual
Typing, as introduced by Siek et al.], most of the Python code used as
training data operates in an untyped fashion, so models may understand
the dynamic flow of optional values but not their static type
annotations. Test 5, below, tests the models understanding of
`Optional` types annotations.^[The trailing colon makes a type
expression the only valid completion; function declarations with a
colon and no type, like `def fn(x:)` are not valid python. Since we’ve
already seen a usage of `get_square` that is passed a None value, it
wouldn’t be type-valid to complete the program with just `int`. So a
model can be tested on its understanding of `Optional` annotations by
seeing if its completion of the partial program includes
`Optional[int]`.]

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

All of the tests in this benchmark suite are composed of three
functions or less, where the largest function is seven lines long.

We measure the difficulty of these tests by measuring how
models of different sizes do on them. For many tests in this post, we
use the Pythia models, as they are available in a large variety of
sizes and training lengths. For measuring performance at larger sizes,
we've included Qwen2.5-Coder-32B, Llama 3.1 405B Instruct, and
DeepSeek-V3 (671B). Below, you can see the number of passing tests for
each model.
\todo{more through exploration of why?}

![A bar graph showing how several sizes of model perform on the
 high-level optionality tests](images/hl_model_results.svg){#fig:hl_scale}

In [@Fig:hl_scale], we can see the number of passing tests for each
model. We can see that generally models get better at larger
sizes^[Pythia 12b performs worse than its 6.9b variant, though this
might be due to under-training at that size. Qwen 32B also performs
about as well as Pythia 6.9b, it's not clear if this is due to model
architecture or something else.]. Model performance on these tests is
approximately logarithmic in model size: models of 2.8 billion
parameters can pass about half the tests, but it takes more than 405
billion parameters to pass all of the tests

Next, we want to know how the amount of training affects model
performance on these tests. Luckily, Pythia also provides models at
different training steps, all the way from step 2 to step
143000. Below we can see how Pythia 6.9b performs on the tests during
training:

![A line graph showing how the performance of the Pythia
6.9 model changes during training](images/hl_revision_results.svg){#fig:hl_time}

Again, we see that while the model generally gets better at passing
these tests during training, the performance is not always increasing.
Also note that this plot is quite noisy, so in the sequel, we will
show smoothed charts^[In our case, "smoothed" means that we average
each training step point with the two points before it and the two
after].


## Morally vs Technically Correct

One explanation of why the model gets worse before it gets better is that the
model first learns the concepts need to solve the task, then learns the
language of python --- its syntax, static (under mypy), and dynamic semantics,
and then both.
\todo{cite something here. grokking, double descent, interp?}
Let's make this more concrete.

We say a model produces an answer that is "morally" (vs technically) correct if
the code attempts to solve the problem asked of it. Each test case is paird with a
regex that tests if the model output produces code that touches all of the relevant
concepts.
\todo{put an example here?}
Here, we say the solution is
"technically" correct if it passes `mypy`.

![A graph showing how often the Pythia 6.9b produces code that
typechecks on the tests, vs produces code that shows true
understanding.](images/hl_mypy_vs_grep.svg){#fig:hl_moral}
\todo{write this section}

## Designing Prompts to Extract Optionality Activations
\todo{we can probably just make this a brief part of the related work}
At this point, we’ve figured out how to roughly measure optionality
understanding in the output of various language models, but we still
don’t know what their internal representations might look like or when
they emerge. To do this, we’re going to bring in some ideas described
in Zhou et al’s paper [“Representation Engineering: A Top-Down Approach
to AI Transparency”](https://arxiv.org/abs/2310.01405).

As language models predict each token in a text, they run their tuned
circuits over all the previous text. Tokens are first embedded into a
high-dimensional “token space”, and each layer of the transformer
model is made up of many parallel circuits which transform the
previous layers output into new embeddings in a new space. Each layer
can look not just at the output of the layer directly previous, but
actually all previous layers, through a channel called a residual
stream.

The paper presents two main approaches to interpreting a language
model; circuit-based, and representation-based. Circuit based
interpretability aims to pair down the network to a key set of
circuits which are sufficient to complete a particular task; this
allows practitioners to point to a particular part of the model and
say “this is where \<task\> is done”, much like neuroscientists assign
functionality to different parts of our brain.

On the other hand, representation-based interpretability looks at the
activation values across the network, and how they vary based on
different inputs, to extract “representations” of particular
concepts. The paper shows how representations can be extracted for
concepts like “happiness”, “honesty”, and “fairness”. First, they
construct many prompts which cause the model to act in a way aligned
with the concept, and many which cause the model to act in a way
aligned against the concept. For instance, they might prompt the model
with “Pretend you’re a dishonest person. The Eiffel Tower is” and
“Pretend you’re an honest person. The Eiffel Tower isr”. Then, they
take the internal activations which correspond to each, and try to
extract a high-dimensional vector which points towards the states
which are aligned, and away from the states that are not aligned. This
vector can then be used as a linear model to measure how much of the
concept is present in the model at any given time (for honesty, this
can be a lie-detector). They can also use it, and similar techniques,
to control the amount of the concept in a response, making it more or
less honest, or more or less fair.

![An excerpt from Zhou et al showing the reading outputs for several
 concepts](images/zhou.png)

In our setting, we were able to avoid dealing with the ambiguities of
natural language by only prompting with code. We decided to stick to
analyzing the optionality of individual variable occurrences, instead
of analyzing every expression. Specifically, we tried to capture the
concept “the variable I just generated refers to an optional
quantity”, so our prompts looked like:

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

To generate these kinds of prompts, we started by asking a few
different chat models to generate for us programs that made use of
optionality. We prompted each model with:

```
Generate me 100 typed python programs that use the optional type,
along with type annotations for any undefined functions that they
use. Make sure that the programs are unique, and each involves at
least eight lines of logic. Number each program from 1 to 100. Please
put all the programs in a single file, with a main function that tests
each. Don't include any text before or after the code, just the
code. I will be using mypy with the --strict option to check the code.
```

We queried o1, o1-mini, deepseek-coder, and claude-sonnet using this
prompt, and then combined programs from the output of all of them into
a single file. Then, we took every function and class in the resulting
code file, and created a file with it and any recursive dependencies
and imports from the file. Finally, we took each variable read
occurrence in each function, and generated a prompt with the tokens up
to and including that variable read, and labeled it with whether or
not the mypy-inferred type is an Optional.

## Reading Vector Extraction

To start, let's look at how previous works have extracted reading
vectors from sample activations. In the Zhou representation
engineering paper, the authors extract a reading vector from the
contrastive pairs of activations using principal component
analysis (PCA).

First, they take each pair of honest and dishonest promptings for the
same stimulus, and get the difference between them, creating a set of
contrast vectors. They randomly flip some of these contrast vectors,
so that overall the set will vary a lot along the direction of the
contrast.  Since PCA assumes that the data is centered around the
origin, they then took the mean of all these vectors, and translated
all the vectors backwards along the mean vector, to create a set with
the same variances but centered around the origin.

Next, they use the PCA analysis from the sklearn library to get a set
of “component” vectors, where the vectors are orthogonal to each other
and explain the maximum variance of the samples in each prefix of the
list. Components in PCA are bidirectional (they can come out of the
analysis in either reflection, and both are equally correct), so next
they flip any component vectors that are pointing more towards the
negative samples than the positive samples. Then, they take the first
component, the most important one, and use it as their reading vector.

Our method for prompt generation didn’t admit contrastive pairs like
in the previous methods, but instead just a bunch of unconnected
positive and negative examples. So instead of doing PCA on contrast
vectors, we averaged the positive examples and the negative examples,
and then took the difference of the averages as our base reading
vector. This is called "mass mean probing" in the literature, and
empirically has been shown to generalize better in high dimensional
space than trying to learn a linear model through logistic
regression.^[see the appendix section "Mass Mean Probing vs Linear
Regression" for more on this]

In this reading vector, the impact of each layer based on the
magnitude of difference in that layer, instead of separate a notion of
how "important" that layer is to differentiating positive and negative
examples. So we decided to try a few different methods of normalizing
these layers to improve their overall accuracy as a linear model:

* No normalization; just the projection across the average difference.
* Normalizing each layers vector to a uniform length
* Dividing by the average amount that each layer activates on the positives samples
* Dividing by the average absolute amount that each layer activates on the positive samples
* Dividing by the square root of the average of squares of layer activations

And we found that no normalization actually did the best of all three
scaling methods. In domains like this one where we have a lot less
training data points then dimensions, what techniques will generalize
well to the test data can be hard to predict.

# Related Work

\todo{mention the tigges paper on circuits across scale, the feng and steinhardt papers, etc}

As previously discussed, [“Representation Engineering: A Top-Down
Approach to AI Transparency”](https://arxiv.org/abs/2310.01405) by
Zhou et al is the most closely related work, consolidating some
research on representation interpretability with linear probes. We
apply similar techniques, but to program semantics and dataflow
instead of natural language.

Several techniques exist for constructing linear probes, but after
experimental measurement we followed the mass means probing from [The
Geometry of Truth: Emergent Linear Structure in Large Language Model
Representations of True/False
Datasets](https://openreview.net/forum?id=CeJEfNKstt) by Marks and
Tegmark. The paper discusses several reasons why mass mean probing
might outperform linear regression.

# Experimental Results

We first measure the accuracy of Pythia models of various sizes and
number of pre-training steps. We use a mass-means probe on all layers,
with a linear regression determining the weights of each layer, since
that is the probing method that we found works best overall. While we
measured accuracy for every available Pythia model size, we exclude
the smallest (14 million parameters) from this graph since it would
exist entirely above the top of the graph.

![The performance, measured in binary cross-entropy, of each Pythia
 model size during pretraining. Since this graph is of loss, lower is
 better](images/accuracy_during_pretraining.svg){#fig:models-and-steps}

In [@Fig:models-and-steps], we can see how loss behaves as model size
increases, and the number of pre-training steps increases. Generally,
we see the loss decreases as models get bigger and are trained for
longer. However, models with fewer than 1 billion parameters reach
their lowest loss before the end of training, and loss increases
after. This indicates that these models may be "overtrained", at least
judging by this particular task. This is to be expected as Pythia
trains all model sizes for the same number of steps, so some will be
overtrained while others will be undertrained.

Prior work focused their probing on a single layer, often handpicked
based on prior papers. In our experiments, we decided to probe *all*
layers using a mass means probe, and learn which ones were most
important from the data. We tested two methods for doing so - either
allowing the magnitude of the difference of means vector to determine
the importance of the layer in the final probe, or to learn
coefficients for each layer using linear regression. We found that
which method is more accurate on test data varies over both model size
and number of training steps.

![The performance of pure mass means probing vs mass means probing
 with linear regression for different Pythia model
 sizes](images/mm-vs-mmlr.svg){#fig:mm-vs-mmlr-sizes}

In [@Fig:mm-vs-mmlr-sizes], we can see that pure mass means probing
gives lower loss for smaller models (those with less than 410 million
parameters), but that for larger models weighting layers using linear
regression gives lower loss consistently.

![The performance of the two probing methods on the Pythia 160m model
 for different numbers of pretraining steps. There are regions where
 pure mass means scaling is better, and regions where linear
 regression on layer weights is better.](images/mm-vs-mmlr-160m.svg){#fig:mm-vs-mmlr-160m}

In [@Fig:mm-vs-mmlr-160m;@Fig:mm-vs-mmlr-410], we look at how these
scaling methods perform for different amounts of pretraining, for the
model sizes nearest the boundary. We see that relative merit of each
scaling method can vary significantly over pretraining steps.

![The performance of the two probing methods on the Pythia 410m model
for different numbers of pretraining steps. Pure mass means probing
starts better, but is quickly overtaken by mass means probing with
linear regression on layer weights.](images/mm-vs-mmlr-410m.svg){#fig:mm-vs-mmlr-410}


# References {.unnumbered}
::: {#refs}
:::

\appendix
# Appendix {.appendix}

## Optionality In Python

To see how Optionality appears in Python, Let’s look at an example
program in Python that uses optionality:

```python
class User:
    def __init__(self, name: str, email: Optional[str]) -> None:
    	 self.name = name
        self.email = email

def get_user_email(user: Optional[User]) -> Optional[str]:
    if user is not None and user.email is not None:
        return user.email
    else:
    	  return None
```

In the `get_user_email` function above, we can see from the type
signature that it takes a optional User value, and returns an optional
string. The first thing the function does is check if the input `user`
is None or not. This program was actually generated by o1-mini, so we
can already see that the model understands that the user object is
optional, and that it needs to be checked for None-ness before
anything else can be done.

We can say that there are five variable “occurances” in the program,
each of which can be either optional or not. There’s the first `user`
in the if statement, the second `user` to the right of the `and` in
`user.email`, there’s the `user.email` itself, the `user` on the
second line, and finally the `user.email` on the second line. If we
use Python’s typechecker, mypy, to check the types of each of these
occurrences, we find that they have type `Optional[User]`, `User`,
`Optional[str]`, `User`, and `str` respectively. That is, the first
and third are optional, and the rest are not.


## Detailed High-Level Optionality Test Results

### Across Scale

You can see in @fig:hl_scale that the smallest three models don’t pass any
test. After that, the trend line for tests passed goes upwards, but
it’s not monotonic: Pythia 410m passes only one test, while Pythia
160m passes three, and Pythia 6.9b passes the most tests, with 9,
while Pythia 12b only passes 7. For instance, given the partial code:

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
Pythia 6.9b completes `process_value` as:
```python
def process_value(value):
  if value is None:
    return 0
  elif isinstance(value, str):
    return int(value)
  ...
```
While Pythia 12b completes it as:
```python
def process_value(value):
  return value
```

The code generated by Pythia 6.9b properly handles values of both
NoneType and str and always returns an int, whereas the code generated
by Pythia 12b is the identify function, returning None when the input
is None and returning a string when the input is a string. Neither of
these cases is correct, as the main function expects this to return a
Number that can be added to one.

### Across Time

We say in @fig:hl_time that while the model generally gets better at
passing these tests during training, the performance is not always
increasing.  Zooming in on a particular test, we can see what this
looks like. When asked to complete this code:

*Test 12*
```python
def handle_value(value, guard):
  if guard:
    return count_os("Foobar") * 2
  else:
    return count_os(value) // 2

def main(x: int) -> None:
  if x > 0:
    value = "*" * x
  else:
    value = None

  print(handle_value(value, x < 10))

def count_os(value):
```

Pythia 6.9b at training step 104000 produces the following definition
of `count_os`:

```python
def count_os(value):
  if value is None:
    return 1
  elif isinstance(value, str):
    return len(value)
...
```

While 1000 steps later, it produces a very different definition:

```python
def count_os(value):
  return len([s for s in os.listdir(os.path.join(os.getcwd(), value)) if s.start ...
```

While the first definition handles value being None or a string, the
second definition not only assumes it is a string but that it is a
name of a folder in the current directory. In some sense the model
“knows” that the value parameter is Optional at step 104000, but
“forgets” it during further training. It regains the ability to pass
the test at several points during training, but by the end of
training, it’s back to treating `value` as if it was always a string.

### Common Mistakes

As expected, type annotations are particularly difficult for these
models. When asked to complete the type of get_square in the following
code, no model in the Pythia series can successfully output the
Optional argument type:

*Test 5*
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

These models also find it much easier to deal with a list that
contains some None elements, than to deal with an atomic value that
might be None. Pythia 6.9b consistently passes this test in the
second half of training:

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

But is much more challenged by this code:

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

, intermittently being unable to complete it in a type-safe way up,
including in the second-to-last training step. When another level of
function indirection is added, the model becomes much better at
completing it correctly; Pythia 6.9b consistently completes the
following after step 93000:

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
The names of functions are highly influential in the models
understanding of their type semantics. When test 3 is changed so that
`process_value` is instead called `count_chars`, Pythia 6.9b becomes
unable to correctly complete it on any revision; it likely has a bias
from its training data that functions called `count_chars` always take
non-optional strings. Similarly, when test 4 is changed so that
process_values becomes string_complexity, it goes from consistently
passing to almost always failing.

## Mass Mean Probing vs Linear Regression

We were initially very surprised to find that mass means probing would
perform better than linear regression. After all, linear regression is
a much more powerful technique for fitting data. And mass means
probing can be seen as giving the direction of best fit in each
dimension independently, without considering other dimensions. The
more dimensions you consider at one time, the better your model fit
can be. But repeatedly in our data, we found that mass means probing
outperformed linear regression on the test data.
